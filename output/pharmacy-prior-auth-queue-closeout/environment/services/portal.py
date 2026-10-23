#!/usr/bin/env python3
"""Portal Service - accepts prior authorization decision submissions on port 5004."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

SUBMISSIONS_FILE = "/app/data/submissions.jsonl"


class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "portal"}).encode())
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/submit":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                submission = json.loads(body)
                required = ["case_id", "decision_code", "reason_code"]
                if all(field in submission for field in required):
                    with open(SUBMISSIONS_FILE, "a") as f:
                        f.write(json.dumps(submission) + "\n")
                    self.send_response(201)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "accepted"}).encode())
                else:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing required fields"}).encode())
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("localhost", 5004), PortalHandler)
    print("Portal service running on port 5004")
    server.serve_forever()
