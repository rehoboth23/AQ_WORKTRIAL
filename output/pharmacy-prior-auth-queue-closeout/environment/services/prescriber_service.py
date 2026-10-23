#!/usr/bin/env python3
"""Prescriber Service - provides patient medication history on port 5002."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA_FILE = "/app/data/prescriber.json"


class PrescriberHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "prescriber"}).encode())
            return

        path_parts = self.path.strip("/").split("/")
        if len(path_parts) == 2 and path_parts[0] == "prescriber":
            patient_id = path_parts[1]
            with open(DATA_FILE) as f:
                prescriber_data = json.load(f)
            for entry in prescriber_data:
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
    server = HTTPServer(("localhost", 5002), PrescriberHandler)
    print("Prescriber service running on port 5002")
    server.serve_forever()
