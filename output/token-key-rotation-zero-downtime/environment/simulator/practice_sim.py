#!/usr/bin/env python3
"""Practice client simulator for the HMAC-SHA256 token service.

Runs ~45 s of issue/verify/revoke cycles while the agent performs
key rotation, then reports any verification mismatches.
All operations are logged to /app/simulator/practice_log.jsonl.
"""

import base64
import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8901"
LOG_FILE = "/app/simulator/practice_log.jsonl"
DURATION = 45


def b64url_decode(s):
    """Decode base64url with padding."""
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def decode_token(tok):
    """Decode a token, return (header, payload) or (None, None)."""
    parts = tok.split(".")
    if len(parts) != 3:
        return None, None
    try:
        header = json.loads(b64url_decode(parts[0]))
        payload = json.loads(b64url_decode(parts[1]))
        return header, payload
    except Exception:
        return None, None


def post(endpoint, body):
    """Make a POST request, return (response_dict, connection_error_bool)."""
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            return json.loads(raw), False
    except Exception as exc:
        return {"error": str(exc), "connection_error": True}, True


def get(endpoint):
    """Make a GET request, return (response_dict, connection_error_bool)."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}{endpoint}", timeout=5) as resp:
            raw = resp.read()
            return json.loads(raw), False
    except Exception as exc:
        return {"error": str(exc), "connection_error": True}, True


def main():
    ops = []
    mismatches = []
    tokens = {}  # jti -> {token, kid, iat, exp, sub, revoked}
    t0 = time.time()

    def now():
        return time.time() - t0

    def log(entry):
        entry["t"] = round(now(), 3)
        entry["wall_t"] = time.time()
        ops.append(entry)

    def issue(sub, phase=""):
        resp, err = post("/issue", {"sub": sub})
        if err:
            log({"op": "issue", "sub": sub, "phase": phase,
                 "error": resp.get("error"), "connection_error": True})
            return None
        tok = resp.get("token", "")
        hdr, pay = decode_token(tok)
        if hdr is None:
            log({"op": "issue", "sub": sub, "phase": phase, "error": "bad_token"})
            return None
        jti = resp.get("jti") or pay.get("jti")
        rec = {
            "token": tok,
            "kid": hdr.get("kid"),
            "iat": pay.get("iat"),
            "exp": pay.get("exp"),
            "sub": sub,
            "revoked": False,
        }
        tokens[jti] = rec
        log({"op": "issue", "jti": jti, "kid": rec["kid"], "iat": rec["iat"],
             "exp": rec["exp"], "sub": sub, "phase": phase})
        return jti

    def verify(jti, expected, phase, reason=""):
        if jti not in tokens:
            return
        resp, err = post("/verify", {"token": tokens[jti]["token"]})
        actual = resp.get("valid") if not err else None
        log({"op": "verify", "jti": jti, "kid": tokens[jti]["kid"],
             "expected": expected, "actual": actual,
             "phase": phase, "reason": reason, "connection_error": err})
        if err:
            mismatches.append({"t": now(), "jti": jti, "kid": tokens[jti]["kid"],
                               "expected": expected, "actual": None,
                               "reason": "connection_error"})
        elif actual != expected:
            mismatches.append({"t": now(), "jti": jti, "kid": tokens[jti]["kid"],
                               "expected": expected, "actual": actual,
                               "phase": phase, "reason": reason})

    def revoke(jti, phase=""):
        if jti not in tokens:
            return
        resp, err = post("/revoke", {"jti": jti})
        tokens[jti]["revoked"] = True
        log({"op": "revoke", "jti": jti, "kid": tokens[jti]["kid"],
             "phase": phase, "success": resp.get("success") if not err else False})

    def keyset(phase=""):
        resp, err = get("/.well-known/keyset")
        kids = ([k.get("kid") for k in resp.get("keys", [])]
                if not err and "keys" in resp else [])
        log({"op": "keyset", "kids": kids, "phase": phase, "connection_error": err})
        return kids

    def verify_all(phase, reason_prefix=""):
        ct = time.time()
        for jti, info in list(tokens.items()):
            if info["exp"] is not None and ct >= info["exp"]:
                continue
            expected = not info["revoked"]
            r = f"{reason_prefix}{'revoked' if info['revoked'] else 'valid'}"
            verify(jti, expected, phase, r)

    # ── Phase 1: Pre-Rotation Baseline (0 – 5 s) ──
    early = []
    for i in range(6):
        j = issue(f"early-{i}", "pre-rotation")
        if j:
            early.append(j)
        time.sleep(0.1)

    for j in early:
        verify(j, True, "pre-rotation", "baseline valid")

    for j in early[:2]:
        revoke(j, "pre-rotation")
    for j in early[:2]:
        verify(j, False, "pre-rotation", "revoked pre-rotation")

    keyset("pre-rotation")
    time.sleep(3)

    # ── Phase 2: Monitoring (5 – 10 s) ──
    mid = []
    for i in range(4):
        j = issue(f"mid-{i}", "monitoring-early")
        if j:
            mid.append(j)
        time.sleep(0.1)

    keyset("monitoring-early")
    verify_all("monitoring-early", "early-monitor ")
    time.sleep(4)

    # ── Phase 3: Overlap (10 – 25 s) ──
    keyset("overlap-start")

    overlap = []
    for i in range(4):
        j = issue(f"overlap-{i}", "overlap")
        if j:
            overlap.append(j)
        time.sleep(0.1)

    verify_all("overlap", "overlap ")

    # Revoke several tokens during overlap (>= 3 for coverage)
    ct = time.time()
    active = [j for j, inf in tokens.items()
              if not inf["revoked"] and inf["exp"] is not None and ct < inf["exp"]]
    overlap_revoked = []
    for j in active[:5]:
        revoke(j, "during-overlap")
        overlap_revoked.append(j)
        verify(j, False, "overlap-revocation",
               "revoked-during-overlap must reject")

    keyset("overlap-mid")
    time.sleep(3)

    verify_all("overlap-late", "overlap-late ")
    keyset("overlap-late")
    time.sleep(3)

    # ── Phase 4: Post-Rotation Early (25 – 37 s) ──
    keyset("post-rotation-early")

    late = []
    for i in range(3):
        j = issue(f"late-{i}", "post-rotation")
        if j:
            late.append(j)
        time.sleep(0.1)

    verify_all("post-rotation-early", "post-early ")
    time.sleep(5)

    # ── Phase 5: Post-Rotation Final (37 – 45 s) ──
    keyset("post-rotation-mid")

    post_tokens = []
    for i in range(3):
        j = issue(f"post-{i}", "post-rotation-final")
        if j:
            post_tokens.append(j)
        time.sleep(0.1)

    verify_all("post-rotation-final", "post-final ")
    keyset("post-rotation-final")

    remaining = DURATION - now()
    if remaining > 0:
        time.sleep(remaining)

    keyset("end")

    # ── Write Log & Report ──
    with open(LOG_FILE, "w") as fh:
        for op in ops:
            fh.write(json.dumps(op) + "\n")
        fh.flush()

    conn_errs = sum(1 for o in ops if o.get("connection_error"))
    overlap_rev_count = sum(
        1 for o in ops
        if o["op"] == "revoke" and "during-overlap" in o.get("phase", ""))
    keyset_count = sum(1 for o in ops if o["op"] == "keyset")

    near_expiry_overlap = 0
    for o in ops:
        if o["op"] != "verify":
            continue
        phase = o.get("phase", "")
        if "overlap" not in phase and "monitoring" not in phase:
            continue
        jti = o.get("jti")
        if jti and jti in tokens:
            info = tokens[jti]
            wall_t = o.get("wall_t", 0)
            remaining_life = info["exp"] - wall_t
            lifetime = info["exp"] - info["iat"]
            if lifetime > 0 and remaining_life > 0 and remaining_life < lifetime * 0.5:
                near_expiry_overlap += 1

    print()
    print("=" * 55)
    print("  Practice Simulator Report")
    print("=" * 55)
    print(f"  Duration           : {now():.1f} s")
    print(f"  Total Operations   : {len(ops)}")
    print(f"  Connection Errors  : {conn_errs}")
    print(f"  Overlap Revocations: {overlap_rev_count}")
    print(f"  Keyset Fetches     : {keyset_count}")
    print(f"  Near-Expiry Checks : {near_expiry_overlap}")
    print(f"  Mismatches         : {len(mismatches)}")
    print("=" * 55)

    if mismatches:
        print(f"\n  ⚠  {len(mismatches)} MISMATCH(ES) DETECTED:\n")
        for m in mismatches:
            print(f"    t={m['t']:.1f}s  JTI={m.get('jti', '?')}  "
                  f"kid={m.get('kid', '?')}  "
                  f"Expected={m['expected']}  Actual={m['actual']}  "
                  f"({m.get('reason', '')})")
        sys.exit(1)
    else:
        print("\n  ✓  All Verifications Matched Expected Results.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
