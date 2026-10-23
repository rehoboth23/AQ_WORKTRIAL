#!/usr/bin/env python3
"""Formulary Service - provides drug formulary data on port 5001."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA_FILE = "/app/data/formulary.json"


class FormularyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "formulary"}).encode())
            return

        path_parts = self.path.strip("/").split("/")
        if len(path_parts) == 2 and path_parts[0] == "formulary":
            drug_id = path_parts[1]
            with open(DATA_FILE) as f:
                formulary = json.load(f)
            for drug in formulary:
                if drug["drug_id"] == drug_id:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(drug).encode())
                    return
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Drug not found"}).encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("localhost", 5001), FormularyHandler)
    print("Formulary service running on port 5001")
    server.serve_forever()
