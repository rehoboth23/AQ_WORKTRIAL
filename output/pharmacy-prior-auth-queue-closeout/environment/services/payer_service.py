#!/usr/bin/env python3
"""Payer Service - provides patient plan tier data on port 5003."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA_FILE = "/app/data/payer.json"


class PayerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "payer"}).encode())
            return

        path_parts = self.path.strip("/").split("/")
        if len(path_parts) == 2 and path_parts[0] == "payer":
            patient_id = path_parts[1]
            with open(DATA_FILE) as f:
                payer_data = json.load(f)
            for entry in payer_data:
                if entry["patient_id"] == patient_id:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(entry).encode())
                    return
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Patient not found"}).encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("localhost", 5003), PayerHandler)
    print("Payer service running on port 5003")
    server.serve_forever()
