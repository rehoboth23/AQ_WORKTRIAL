#!/usr/bin/env python3
"""Practice load generator for the session service migration.

Generates a deterministic stream of operations from a seed, sends them
to the service, and records each request and response to a JSON file.

The migration request is sent in a background thread so that requests
continue to arrive while migration is in progress — this exercises the
dual-write path.

Usage:
  python3 loadgen.py --seed 1 --host localhost --port 8080 --output /tmp/log.json
  python3 loadgen.py --seed 1 --stream-only --output /tmp/stream.json
"""

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request


# ---------------------------------------------------------------------- #
#  stream generation  (deterministic from seed)
# ---------------------------------------------------------------------- #
def generate_stream(seed, num_requests=10000):
    """Return a deterministic list of operation dicts.

    Each dict has:
        op          – 'create' | 'read' | 'update' | 'delete' | 'migrate'
        seq         – sequence number (0-based)
        session_id  – stream-level id (for create the real id is assigned
                      by the service; the loadgen maps it at run time)
        data        – present for create / update
        ttl         – present for create
    """
    rng = random.Random(seed)
    stream = []
    active = []          # list of stream session-ids currently "alive"
    migrate_at = num_requests // 3

    ttl_pool = [300, 300, 300, 300, 300, 5, 5, 5, 2, 2, 2]

    i = 0
    while i < num_requests:
        # ----- migration marker -----
        if i == migrate_at:
            stream.append({"op": "migrate", "seq": i})
            i += 1
            continue

        r = rng.random()

        # write probability depends on distance from migration point
        dist = i - migrate_at
        if -50 <= dist <= 50:
            write_prob = 0.50       # burst
        elif -200 <= dist <= 200:
            write_prob = 0.30       # medium
        else:
            write_prob = 0.15       # low

        # ----- create -----
        if r < 0.20 and len(active) < 200:
            ttl = rng.choice(ttl_pool)
            sid = f"s-{seed}-{len(stream)}"
            data = {"value": rng.randint(0, 9999), "n": i}
            stream.append(
                {
                    "op": "create",
                    "seq": i,
                    "session_id": sid,
                    "data": data,
                    "ttl": ttl,
                }
            )
            active.append(sid)
            i += 1

        # ----- update (possibly followed by read-after-write) -----
        elif r < 0.20 + write_prob * 0.4 and active:
            idx = rng.randint(0, len(active) - 1)
            sid = active[idx]
            data = {"value": rng.randint(0, 9999), "n": i}
            stream.append(
                {
                    "op": "update",
                    "seq": i,
                    "session_id": sid,
                    "data": data,
                }
            )
            i += 1
            # read-after-write pair
            if rng.random() < 0.30 and i < num_requests and i != migrate_at:
                stream.append(
                    {"op": "read", "seq": i, "session_id": sid}
                )
                i += 1

        # ----- read -----
        elif r < 0.90 and active:
            idx = rng.randint(0, len(active) - 1)
            sid = active[idx]
            stream.append({"op": "read", "seq": i, "session_id": sid})
            i += 1

        # ----- delete -----
        elif active:
            idx = rng.randint(0, len(active) - 1)
            sid = active.pop(idx)
            stream.append({"op": "delete", "seq": i, "session_id": sid})
            i += 1

        # ----- nothing to read/update/delete → create -----
        else:
            ttl = rng.choice(ttl_pool)
            sid = f"s-{seed}-{len(stream)}"
            data = {"value": rng.randint(0, 9999), "n": i}
            stream.append(
                {
                    "op": "create",
                    "seq": i,
                    "session_id": sid,
                    "data": data,
                    "ttl": ttl,
                }
            )
            active.append(sid)
            i += 1

    return stream


# ---------------------------------------------------------------------- #
#  HTTP helpers
# ---------------------------------------------------------------------- #
def _send_one(host, port, op, actual_sid=None):
    """Send a single request; return (status, body_dict, ts, error_str)."""
    ts = time.time()
    base = f"http://{host}:{port}"
    error = None

    try:
        if op["op"] == "create":
            payload = json.dumps({"data": op["data"], "ttl": op["ttl"]}).encode()
            req = urllib.request.Request(
                f"{base}/sessions", data=payload, method="POST"
            )
            req.add_header("Content-Type", "application/json")

        elif op["op"] == "read":
            req = urllib.request.Request(
                f"{base}/sessions/{actual_sid}", method="GET"
            )

        elif op["op"] == "update":
            payload = json.dumps({"data": op["data"]}).encode()
            req = urllib.request.Request(
                f"{base}/sessions/{actual_sid}", data=payload, method="PUT"
            )
            req.add_header("Content-Type", "application/json")

        elif op["op"] == "delete":
            req = urllib.request.Request(
                f"{base}/sessions/{actual_sid}", method="DELETE"
            )

        elif op["op"] == "migrate":
            req = urllib.request.Request(
                f"{base}/admin/migrate", data=b"{}", method="POST"
            )
            req.add_header("Content-Type", "application/json")
        else:
            return 0, {}, ts, f"unknown op: {op['op']}"

        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            raw = resp.read().decode()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"raw": raw}

    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode() if e.fp else ""
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
    except Exception as exc:  # connection refused, timeout, etc.
        status = 0
        body = {"error": str(exc)}
        error = str(exc)

    return status, body, ts, error


# ---------------------------------------------------------------------- #
#  full run
# ---------------------------------------------------------------------- #
def run_loadgen(seed, host, port, output_file, num_requests=10000):
    stream = generate_stream(seed, num_requests)
    log = []
    sid_map = {}  # stream-sid → actual service uuid

    migrate_done = threading.Event()
    migrate_box = [None]  # (status, body, ts, error)

    for op in stream:
        if op["op"] == "migrate":
            # fire migrate in a background thread so requests keep flowing
            op_snapshot = dict(op)

            def _bg(o=op_snapshot):
                migrate_box[0] = _send_one(host, port, o)
                migrate_done.set()

            t = threading.Thread(target=_bg, daemon=True)
            t.start()

            log.append(
                {
                    "seq": op["seq"],
                    "ts": time.time(),
                    "op": "migrate",
                    "status": None,
                    "resp_body": None,
                    "_pending": True,
                }
            )
            continue

        stream_sid = op.get("session_id")
        actual_sid = sid_map.get(stream_sid, stream_sid)

        status, body, ts, err = _send_one(host, port, op, actual_sid)

        # learn the real id from a successful create
        if op["op"] == "create" and status == 201:
            real = body.get("session_id")
            if real:
                sid_map[stream_sid] = real
                actual_sid = real

        entry = {
            "seq": op["seq"],
            "ts": ts,
            "op": op["op"],
            "session_id": (
                body.get("session_id") if op["op"] == "create" else actual_sid
            ),
            "data": op.get("data"),
            "ttl": op.get("ttl"),
            "status": status,
            "resp_body": body,
        }
        if err:
            entry["error"] = err
        log.append(entry)

    # wait for migrate to finish (60 s is generous)
    migrate_done.wait(timeout=60)
    if migrate_box[0] is not None:
        status, body, ts, err = migrate_box[0]
        for e in log:
            if e.get("_pending"):
                e["status"] = status
                e["resp_body"] = body
                e["ts"] = ts
                e.pop("_pending", None)
                if err:
                    e["error"] = err
                break

    with open(output_file, "w") as f:
        json.dump(log, f, indent=2, sort_keys=True)

    total = len(log)
    failures = sum(
        1 for e in log if e.get("error") or e.get("status", 0) == 0
    )
    print(f"Load test complete: {total} requests, {failures} failures")
    print(f"Log written to {output_file}")


# ---------------------------------------------------------------------- #
#  CLI
# ---------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Session service load generator")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--output", required=True)
    ap.add_argument("--num-requests", type=int, default=10000)
    ap.add_argument("--stream-only", action="store_true")
    args = ap.parse_args()

    if args.stream_only:
        stream = generate_stream(args.seed, args.num_requests)
        with open(args.output, "w") as f:
            json.dump(stream, f, indent=2, sort_keys=True)
        print(f"Stream written to {args.output} ({len(stream)} operations)")
    else:
        run_loadgen(
            args.seed,
            args.host,
            args.port,
            args.output,
            args.num_requests,
        )


if __name__ == "__main__":
    main()
