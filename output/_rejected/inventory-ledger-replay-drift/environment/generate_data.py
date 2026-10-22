#!/usr/bin/env python3
"""Generate initial warehouse ledger data for the /app/data/ directory.

Creates a realistic set of events including a message redelivery
that produced a duplicate log entry, and a couple of late corrections.
"""

import json
from pathlib import Path

DATA_DIR = Path("/app/data")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Events in chronological order.
    # The second evt002 entry is a redelivery of the original SHIP event.
    events = [
        {
            "event_id": "evt001",
            "type": "RECEIVE",
            "sku": "WIDGET-A",
            "qty": 100,
            "timestamp": "2025-01-15T10:00:00+00:00",
        },
        {
            "event_id": "evt002",
            "type": "SHIP",
            "sku": "WIDGET-A",
            "qty": 30,
            "timestamp": "2025-01-15T11:00:00+00:00",
        },
        {
            "event_id": "evt003",
            "type": "RETURN",
            "sku": "WIDGET-A",
            "qty": 10,
            "timestamp": "2025-01-16T09:00:00+00:00",
        },
        {
            "event_id": "evt004",
            "type": "RECEIVE",
            "sku": "WIDGET-B",
            "qty": 50,
            "timestamp": "2025-01-16T10:00:00+00:00",
        },
        {
            "event_id": "evt005",
            "type": "SHIP",
            "sku": "WIDGET-B",
            "qty": 20,
            "timestamp": "2025-01-17T08:00:00+00:00",
        },
        {
            "event_id": "cor001",
            "type": "CORRECT",
            "ref_id": "evt001",
            "sku": "WIDGET-A",
            "new_qty": 80,
            "timestamp": "2025-01-18T10:00:00+00:00",
        },
        {
            "event_id": "evt002",
            "type": "SHIP",
            "sku": "WIDGET-A",
            "qty": 30,
            "timestamp": "2025-01-18T11:05:00+00:00",
        },
        {
            "event_id": "cor002",
            "type": "CORRECT",
            "ref_id": "evt004",
            "sku": "WIDGET-B",
            "new_qty": 40,
            "timestamp": "2025-01-19T09:00:00+00:00",
        },
    ]

    # Write events log
    events_file = DATA_DIR / "events.jsonl"
    with open(events_file, "w") as f:
        for ev in events:
            f.write(json.dumps(ev, sort_keys=True) + "\n")

    # Snapshot as the live handler computed it.
    # E1:  WIDGET-A += 100             -> 100
    # E2:  WIDGET-A -= 30              -> 70
    # E3:  WIDGET-A += 10              -> 80
    # E4:  WIDGET-B += 50              -> 50
    # E5:  WIDGET-B -= 20              -> 30
    # C1:  CORRECT evt001->80  d=-20   -> 60
    # E2(dup): already applied, skip
    # C2:  CORRECT evt004->40  d=-10   -> 20
    snapshot = {"WIDGET-A": 60, "WIDGET-B": 20}
    with open(DATA_DIR / "snapshot.json", "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)

    # Applied set (7 distinct event IDs — the duplicate evt002 does not
    # add a new key because dict keys are unique).
    applied = {ev["event_id"]: True for ev in events}
    with open(DATA_DIR / "applied.json", "w") as f:
        json.dump(applied, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
