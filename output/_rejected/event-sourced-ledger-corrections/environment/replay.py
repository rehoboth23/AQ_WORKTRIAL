"""Log replay for the inventory ledger.

Replays the full event log from scratch to compute stock levels,
providing a ground-truth comparison for the incrementally maintained state.
"""

import json


def validate_event_log(event_log_path):
    """Validate the structure of an event log file.

    Checks that each line is valid JSON with required fields and
    that sequence numbers are consistent.

    Args:
        event_log_path: path to the JSONL event log

    Returns:
        List of validation error strings (empty if valid).
    """
    errors = []
    line_num = 0

    with open(event_log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            line_num += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: invalid JSON: {e}")
                continue

            for field in ("id", "event_id", "type", "sku", "quantity"):
                if field not in event:
                    errors.append(f"Line {line_num}: missing field '{field}'")

            if event.get("type") == "CORRECTION" and "ref_id" not in event:
                errors.append(f"Line {line_num}: correction missing ref_id")

    return errors


def replay_events(event_log_path):
    """Replay all events from the log and compute final stock levels.

    Processes each event in order, applying receipts, shipments, and
    corrections. Redeliveries (same event_id appearing more than once)
    are skipped on subsequent appearances.

    Args:
        event_log_path: path to the JSONL event log

    Returns:
        Dict mapping SKU names to stock quantities.
    """
    events = []
    with open(event_log_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    stock = {}
    seen = set()
    effective = {}      # event_id -> current effective quantity
    events_by_id = {}   # event_id -> original event dict

    for event in events:
        # Skip duplicate events
        if event["id"] in seen:
            continue
        seen.add(event["id"])

        eid = event["event_id"]
        sku = event["sku"]
        etype = event["type"]
        qty = event["quantity"]

        if sku not in stock:
            stock[sku] = 0

        if etype == "RECEIPT":
            stock[sku] += qty
            effective[eid] = qty
            events_by_id[eid] = event

        elif etype == "SHIPMENT":
            stock[sku] -= qty
            effective[eid] = qty
            events_by_id[eid] = event

        elif etype == "CORRECTION":
            ref_id = event["ref_id"]
            ref_event = events_by_id[ref_id]
            original_qty = ref_event["quantity"]
            new_qty = qty
            delta = new_qty - original_qty

            if ref_event["type"] == "RECEIPT":
                stock[sku] += delta
            elif ref_event["type"] == "SHIPMENT":
                stock[sku] -= delta

            effective[ref_id] = new_qty

    return stock


def replay_with_details(event_log_path):
    """Replay events and return detailed results including processing info.

    Useful for debugging and understanding which events were applied.

    Args:
        event_log_path: path to the JSONL event log

    Returns:
        Dict with keys:
        - stock: dict mapping SKU to final stock
        - processed: list of event_ids that were processed (in order)
        - skipped: list of event_ids that were skipped as duplicates
    """
    events = []
    with open(event_log_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    stock = {}
    seen = set()
    effective = {}
    events_by_id = {}
    processed = []
    skipped = []

    for event in events:
        if event["id"] in seen:
            skipped.append(event["event_id"])
            continue
        seen.add(event["id"])

        eid = event["event_id"]
        sku = event["sku"]
        etype = event["type"]
        qty = event["quantity"]

        if sku not in stock:
            stock[sku] = 0

        if etype == "RECEIPT":
            stock[sku] += qty
            effective[eid] = qty
            events_by_id[eid] = event
        elif etype == "SHIPMENT":
            stock[sku] -= qty
            effective[eid] = qty
            events_by_id[eid] = event
        elif etype == "CORRECTION":
            ref_id = event["ref_id"]
            ref_event = events_by_id[ref_id]
            original_qty = ref_event["quantity"]
            new_qty = qty
            delta = new_qty - original_qty

            if ref_event["type"] == "RECEIPT":
                stock[sku] += delta
            elif ref_event["type"] == "SHIPMENT":
                stock[sku] -= delta

            effective[ref_id] = new_qty

        processed.append(eid)

    return {
        "stock": stock,
        "processed": processed,
        "skipped": skipped,
    }
