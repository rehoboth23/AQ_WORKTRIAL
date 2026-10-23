#!/usr/bin/env python3
"""Stock ledger service — serves stock entries read-only from JSON files."""
import json
import os

from flask import Flask, request, jsonify

app = Flask(__name__)
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")


@app.route("/entries")
def get_entries():
    month = request.args.get("month")
    if not month:
        return jsonify({"error": "month parameter required"}), 400
    filepath = os.path.join(DATA_DIR, f"stock_{month}.json")
    if not os.path.exists(filepath):
        return jsonify([])
    with open(filepath) as f:
        entries = json.load(f)
    return jsonify(entries)


@app.route("/")
def index():
    return jsonify({"service": "ledger", "status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
