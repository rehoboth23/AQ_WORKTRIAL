#!/usr/bin/env python3
"""Filing portal service — two-step submit/confirm with audit log and seeded 503 faults."""
import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

# ---------------------------------------------------------------------------
# In-memory state (reset via POST /reset)
# ---------------------------------------------------------------------------
submissions: dict = {}          # request_id (or generated key) -> submission dict
audit_log: list = []            # list of audit-entry dicts
submit_counters: dict = {}      # key -> call count for fault injection
confirm_counters: dict = {}     # key -> call count for fault injection


def _load_config():
    filepath = os.path.join(DATA_DIR, "portal_config.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return {"submit_faults": [], "confirm_faults": []}


def _reset_state():
    global submissions, audit_log, submit_counters, confirm_counters
    submissions = {}
    audit_log = []
    submit_counters = {}
    confirm_counters = {}


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    request_id = data.get("request_id")
    month = data.get("month")
    duty_lines = data.get("duty_lines", [])
    total_duty = data.get("total_duty", 0)

    if not month:
        return jsonify({"error": "month required"}), 400

    # ---- Idempotency check ----
    if request_id and request_id in submissions:
        existing = submissions[request_id]
        audit_log.append({
            "action": "submit",
            "request_id": request_id,
            "month": month,
            "reference": existing["reference"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "200",
            "duplicate": False,
            "idempotent": True,
        })
        return jsonify({"reference": existing["reference"]}), 200

    # ---- Create submission ----
    reference = f"REF-{month}-{uuid.uuid4().hex[:8]}"
    sub = {
        "reference": reference,
        "month": month,
        "duty_lines": duty_lines,
        "total_duty": total_duty,
        "confirmed": False,
        "confirmation_code": None,
        "request_id": request_id,
    }
    key = request_id if request_id else f"_auto_{uuid.uuid4().hex[:8]}"
    submissions[key] = sub

    # ---- Fault injection ----
    config = _load_config()
    call_key = f"submit_{month}"
    submit_counters[call_key] = submit_counters.get(call_key, 0) + 1
    call_idx = submit_counters[call_key] - 1

    if call_idx in config.get("submit_faults", []):
        audit_log.append({
            "action": "submit",
            "request_id": request_id,
            "month": month,
            "reference": reference,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "503",
            "fault": True,
        })
        return jsonify({"error": "Service temporarily unavailable"}), 503

    audit_log.append({
        "action": "submit",
        "request_id": request_id,
        "month": month,
        "reference": reference,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "200",
        "duplicate": False,
    })
    return jsonify({"reference": reference}), 200


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------
@app.route("/confirm", methods=["POST"])
def confirm():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    reference = data.get("reference")
    request_id = data.get("request_id")

    if not reference:
        return jsonify({"error": "reference required"}), 400

    # ---- Find submission by reference ----
    sub = None
    for _key, s in submissions.items():
        if s["reference"] == reference:
            sub = s
            break

    if sub is None:
        return jsonify({"error": "Reference not found"}), 404

    already_confirmed = sub["confirmed"]

    # ---- Perform confirmation (even if faulting) ----
    if not already_confirmed:
        sub["confirmed"] = True
        sub["confirmation_code"] = f"CONF-{sub['month']}-{uuid.uuid4().hex[:8]}"

    # ---- Determine duplicate flag ----
    is_duplicate = False
    if already_confirmed:
        # This is a retry / repeat confirm
        if request_id and request_id == sub.get("request_id"):
            is_duplicate = False   # idempotent retry
        else:
            is_duplicate = True    # non-idempotent repeat

    # ---- Fault injection ----
    config = _load_config()
    call_key = f"confirm_{reference}"
    confirm_counters[call_key] = confirm_counters.get(call_key, 0) + 1
    call_idx = confirm_counters[call_key] - 1

    if call_idx in config.get("confirm_faults", []):
        audit_entry = {
            "action": "confirm",
            "request_id": request_id,
            "reference": reference,
            "confirmation_code": sub["confirmation_code"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "503",
            "fault": True,
            "duplicate": is_duplicate,
        }
        audit_log.append(audit_entry)
        return jsonify({"error": "Service temporarily unavailable"}), 503

    audit_entry = {
        "action": "confirm",
        "request_id": request_id,
        "reference": reference,
        "confirmation_code": sub["confirmation_code"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "200",
        "duplicate": is_duplicate,
    }
    if not is_duplicate and already_confirmed and request_id and request_id == sub.get("request_id"):
        audit_entry["idempotent"] = True
    audit_log.append(audit_entry)
    return jsonify({"confirmation_code": sub["confirmation_code"]}), 200


# ---------------------------------------------------------------------------
# Query endpoints
# ---------------------------------------------------------------------------
@app.route("/submissions")
def get_submissions():
    return jsonify(list(submissions.values()))


@app.route("/audit")
def get_audit():
    return jsonify(audit_log)


@app.route("/reset", methods=["POST"])
def reset():
    _reset_state()
    return jsonify({"status": "reset"}), 200


@app.route("/")
def index():
    return jsonify({"service": "portal", "status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
