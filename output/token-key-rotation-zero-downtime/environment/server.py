#!/usr/bin/env python3
"""HMAC-SHA256 Token Service

Provides token issuance, verification, and revocation using HMAC-SHA256 signing keys.
Configuration is loaded from /app/config.json and /app/revocations.json.
Send SIGHUP to the process to hot-reload both files.
"""

import http.server
import socketserver
import json
import hmac
import hashlib
import base64
import os
import time
import uuid
import signal
import threading

HOST = "0.0.0.0"
PORT = 8901
CONFIG_PATH = "/app/config.json"
REVOCATIONS_PATH = "/app/revocations.json"
PID_PATH = "/app/server.pid"

# Shared state
state_lock = threading.Lock()
config = {}
revocations = []


def load_state_from_disk():
    """Read config and revocations from disk and return them."""
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    with open(REVOCATIONS_PATH, "r") as f:
        rev = json.load(f)
    return cfg, rev


def reload_state():
    """Reload config and revocations from disk into globals."""
    global config, revocations
    try:
        cfg, rev = load_state_from_disk()
        config = cfg
        revocations = rev
    except Exception:
        pass  # keep previous state on error


def b64url_encode(data):
    """Base64url encode without padding."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s):
    """Base64url decode, adding padding as needed."""
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


class TokenHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the token service."""

    def do_GET(self):
        if self.path == "/.well-known/keyset":
            self._handle_keyset()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/issue":
            self._handle_issue()
        elif self.path == "/verify":
            self._handle_verify()
        elif self.path == "/revoke":
            self._handle_revoke()
        else:
            self.send_error(404)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            body = self.rfile.read(length)
            return json.loads(body)
        return {}

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_issue(self):
        data = self._read_json()
        sub = data.get("sub", "anonymous")

        with state_lock:
            kid = config["signing_key_id"]
            key_b64 = config["keys"][kid]
            lifetime = config["token_lifetime_seconds"]

        now = int(time.time())
        jti = str(uuid.uuid4())

        header = {"alg": "HS256", "kid": kid, "typ": "JWT"}
        payload = {"sub": sub, "iat": now, "exp": now + lifetime, "jti": jti}

        header_enc = b64url_encode(json.dumps(header, separators=(",", ":")))
        payload_enc = b64url_encode(json.dumps(payload, separators=(",", ":")))

        signing_input = f"{header_enc}.{payload_enc}".encode("ascii")
        key_bytes = b64url_decode(key_b64)
        sig = hmac.new(key_bytes, signing_input, hashlib.sha256).digest()
        sig_enc = b64url_encode(sig)

        token = f"{header_enc}.{payload_enc}.{sig_enc}"
        self._send_json({
            "token": token,
            "jti": jti,
            "kid": kid,
            "iat": now,
            "exp": now + lifetime,
        })

    def _handle_verify(self):
        data = self._read_json()
        token_str = data.get("token", "")

        parts = token_str.split(".")
        if len(parts) != 3:
            self._send_json({"valid": False})
            return

        header_enc, payload_enc, sig_enc = parts

        try:
            header = json.loads(b64url_decode(header_enc))
            payload = json.loads(b64url_decode(payload_enc))
        except Exception:
            self._send_json({"valid": False})
            return

        # Check expiry
        if time.time() >= payload.get("exp", 0):
            self._send_json({"valid": False})
            return

        # Check revocation
        with state_lock:
            is_revoked = payload.get("jti") in revocations
            # Determine the signing key for verification
            signing_kid = config["signing_key_id"]
            if signing_kid not in config["keys"]:
                self._send_json({"valid": False})
                return
            key_b64 = config["keys"][signing_kid]

        if is_revoked:
            self._send_json({"valid": False})
            return

        # Verify HMAC-SHA256 signature
        signing_input = f"{header_enc}.{payload_enc}".encode("ascii")
        key_bytes = b64url_decode(key_b64)
        expected_sig = hmac.new(key_bytes, signing_input, hashlib.sha256).digest()

        try:
            actual_sig = b64url_decode(sig_enc)
        except Exception:
            self._send_json({"valid": False})
            return

        if not hmac.compare_digest(expected_sig, actual_sig):
            self._send_json({"valid": False})
            return

        self._send_json({"valid": True})

    def _handle_revoke(self):
        global revocations
        data = self._read_json()
        jti = data.get("jti", "")

        with state_lock:
            new_revocations = list(revocations) + [jti]
            with open(REVOCATIONS_PATH, "w") as f:
                json.dump(new_revocations, f)
            revocations = new_revocations

        self._send_json({"success": True})

    def _handle_keyset(self):
        with state_lock:
            keys = []
            for kid, k in config["keys"].items():
                keys.append({"kid": kid, "alg": "HS256", "k": k})

        self._send_json({"keys": keys})

    def log_message(self, format, *args):
        pass  # suppress default request logging


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def sighup_handler(signum, frame):
    reload_state()


def main():
    global config, revocations

    # Load initial configuration
    config, revocations = load_state_from_disk()

    # Write PID file
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))

    # Register SIGHUP handler for hot-reload
    signal.signal(signal.SIGHUP, sighup_handler)

    # Start the HTTP server
    server = ThreadedHTTPServer((HOST, PORT), TokenHandler)
    print(f"Token service listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
