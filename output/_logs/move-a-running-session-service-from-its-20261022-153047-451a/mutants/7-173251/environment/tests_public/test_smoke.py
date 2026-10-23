#!/usr/bin/env python3
"""Public smoke test for the session service migration.

Tests the common path only:
  1. Start the service.
  2. Create a session on SQLite.
  3. Call /admin/migrate.
  4. Verify /admin/store returns 'logstore'.
  5. Read the session back from the log store.
  6. Create a new session on the log store.
  7. Delete a session.

Run:  python3 /app/tests_public/test_smoke.py
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = 8080
PYTHON = "/usr/local/bin/python3"
SERVICE = "/app/session_svc.py"


def wait_for_service(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"http://localhost:{PORT}/admin/store")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def api(method, path, body=None, timeout=10):
    url = f"http://localhost:{PORT}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}, dict(resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        return e.code, json.loads(raw) if raw else {}, dict(e.headers)


def main():
    proc = subprocess.Popen(
        [PYTHON, SERVICE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )
    try:
        if not wait_for_service():
            print("FAIL: service did not start")
            return 1

        checks = []

        # 1. create session
        st, body, hdrs = api("POST", "/sessions",
                             {"data": {"user": "alice"}, "ttl": 300})
        assert st == 201, f"create status {st}"
        assert body["data"] == {"user": "alice"}, f"create data {body}"
        sid = body["session_id"]
        assert f"session_id={sid}" in hdrs.get("Set-Cookie", ""), "no cookie"
        checks.append("create session")

        # 2. migrate
        st, body, hdrs = api("POST", "/admin/migrate", {})
        assert st == 200, f"migrate status {st}: {body}"
        assert body.get("status") == "migrated", f"migrate body {body}"
        checks.append("migrate")

        # 3. store check
        st, body, hdrs = api("GET", "/admin/store")
        assert st == 200, f"store status {st}"
        assert body.get("store") == "logstore", f"store body {body}"
        checks.append("store=logstore")

        # 4. read back
        st, body, hdrs = api("GET", f"/sessions/{sid}")
        assert st == 200, f"read status {st}: {body}"
        assert body["session_id"] == sid, f"read sid {body}"
        assert body["data"] == {"user": "alice"}, f"read data {body}"
        checks.append("read back after migrate")

        # 5. create new session on log store
        st, body, hdrs = api("POST", "/sessions",
                             {"data": {"user": "bob"}, "ttl": 300})
        assert st == 201, f"create2 status {st}"
        assert body["data"] == {"user": "bob"}, f"create2 data {body}"
        checks.append("create on logstore")

        # 6. delete
        st, body, hdrs = api("DELETE", f"/sessions/{sid}")
        assert st == 204, f"delete status {st}"
        checks.append("delete")

        # 7. verify deleted
        st, body, hdrs = api("GET", f"/sessions/{sid}")
        assert st == 404, f"read-after-delete status {st}"
        checks.append("404 after delete")

        print(f"\nAll smoke checks passed: {', '.join(checks)}")
        return 0

    except AssertionError as e:
        print(f"FAIL: {e}")
        return 1
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
        proc.wait()


if __name__ == "__main__":
    sys.exit(main())
