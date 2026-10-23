#!/usr/bin/env python3
"""ERP service — serves movements and commodities from JSON files."""
import json
import os

from flask import Flask, request, jsonify

app = Flask(__name__)
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")


@app.route("/movements")
def get_movements():
    month = request.args.get("month")
    if not month:
        return jsonify({"error": "month parameter required"}), 400
    filepath = os.path.join(DATA_DIR, f"movements_{month}.json")
    if not os.path.exists(filepath):
        return jsonify([])
    with open(filepath) as f:
        movements = json.load(f)
    return jsonify(movements)


@app.route("/commodities")
def get_commodities():
    filepath = os.path.join(DATA_DIR, "commodities.json")
    if not os.path.exists(filepath):
        return jsonify({"error": "commodities file not found"}), 500
    with open(filepath) as f:
        commodities = json.load(f)
    return jsonify(commodities)


@app.route("/")
def index():
    return jsonify({"service": "erp", "status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
