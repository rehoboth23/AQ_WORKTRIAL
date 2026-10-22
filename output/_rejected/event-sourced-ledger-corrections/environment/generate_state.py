#!/usr/bin/env python3
"""Generate the initial incremental state from the event log.

Computes state.json by processing events.jsonl through the incremental
path (process_event). Run this once during image build, then delete
this script.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store import EventStore
from ledger import process_event


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_PATH = os.path.join(BASE_DIR, "events.jsonl")
STATE_PATH = os.path.join(BASE_DIR, "state.json")


def main():
    store = EventStore()
    stock = {}

    with open(EVENTS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                event = json.loads(line)
                process_event(event, store, stock)

    with open(STATE_PATH, "w") as f:
        json.dump(stock, f, indent=2, sort_keys=True)

    print(f"Generated state from {store.event_count} unique events")


if __name__ == "__main__":
    main()
