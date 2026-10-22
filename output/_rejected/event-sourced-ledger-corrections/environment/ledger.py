"""Inventory ledger with event-sourced tracking.

Maintains stock levels incrementally and supports verification
against a full log replay. Events are appended to an immutable
log (events.jsonl), and the current state is maintained in
state.json.

Usage:
    python3 ledger.py replay [events_path] [state_path]
    python3 ledger.py verify [events_path] [state_path]
    python3 ledger.py ingest [events_path] [state_path]
    python3 ledger.py summary [state_path]
"""

import json
import sys

from store import EventStore
from replay import replay_events


EVENTS_PATH = "/app/events.jsonl"
STATE_PATH = "/app/state.json"


def load_state(path=STATE_PATH):
    """Load current stock state from file.

    Args:
        path: path to the state JSON file

    Returns:
        Dict mapping SKU names to stock quantities.
        Returns empty dict if file doesn't exist or is invalid.
    """
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(stock, path=STATE_PATH):
    """Save stock state to file.

    Args:
        stock: dict mapping SKU names to stock quantities
        path: path to the state JSON file
    """
    with open(path, "w") as f:
        json.dump(stock, f, indent=2, sort_keys=True)


def process_event(event, store, stock):
    """Process a single event and update stock incrementally.

    Applies the event to the stock dict and registers it in the store.
    Duplicate events (same event_id already seen) are skipped.

    Args:
        event: the event dict to process
        store: the EventStore instance for tracking events
        stock: the stock dict to update (modified in place)

    Returns:
        True if the event was processed, False if it was a duplicate.
    """
    eid = event["event_id"]

    # Skip duplicate events (same event_id already seen)
    if store.has_event(eid):
        return False

    sku = event["sku"]
    etype = event["type"]
    qty = event["quantity"]

    if sku not in stock:
        stock[sku] = 0

    store.add_event(event)

    if etype == "RECEIPT":
        stock[sku] += qty

    elif etype == "SHIPMENT":
        stock[sku] -= qty

    elif etype == "CORRECTION":
        ref_id = event["ref_id"]
        ref_event = store.get_event(ref_id)
        original_qty = ref_event["quantity"]
        new_qty = qty
        delta = new_qty - original_qty

        if ref_event["type"] == "RECEIPT":
            stock[sku] += delta
        elif ref_event["type"] == "SHIPMENT":
            stock[sku] -= delta

        store.update_effective_qty(ref_id, new_qty)

    return True


def ingest_all(store, stock, events_path=EVENTS_PATH):
    """Ingest all events from the log into the incremental state.

    Processes events in order, applying each to the stock dict.
    Duplicate event_ids are skipped.

    Args:
        store: the EventStore instance
        stock: the stock dict to update (modified in place)
        events_path: path to the JSONL event log

    Returns:
        Number of events processed (excluding duplicates).
    """
    count = 0
    with open(events_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                event = json.loads(line)
                if process_event(event, store, stock):
                    count += 1
    return count


def cmd_replay(events_path=EVENTS_PATH, state_path=STATE_PATH):
    """Replay the entire event log and save the result as the new state.

    This discards the current incremental state and rebuilds it
    from scratch by replaying the full event log.

    Args:
        events_path: path to the JSONL event log
        state_path: path to the state JSON file
    """
    stock = replay_events(events_path)
    save_state(stock, state_path)
    print(f"Replayed events and saved state to {state_path}")


def cmd_ingest(events_path=EVENTS_PATH, state_path=STATE_PATH):
    """Rebuild state by incrementally re-processing all events.

    Unlike replay (which uses the replay module), this uses the
    incremental process_event function to rebuild state from scratch.

    Args:
        events_path: path to the JSONL event log
        state_path: path to the state JSON file
    """
    store = EventStore()
    stock = {}
    count = ingest_all(store, stock, events_path)
    save_state(stock, state_path)
    print(f"Ingested {count} events and saved state to {state_path}")


def cmd_verify(events_path=EVENTS_PATH, state_path=STATE_PATH):
    """Verify that incremental state matches a full replay.

    Loads the current state from the state file and compares it against
    a fresh replay of the event log. Any SKUs with differing values
    are reported as mismatches.

    Args:
        events_path: path to the JSONL event log
        state_path: path to the state JSON file
    """
    incremental = load_state(state_path)
    replayed = replay_events(events_path)

    all_skus = sorted(set(list(incremental.keys()) + list(replayed.keys())))

    mismatches = []
    for sku in all_skus:
        inc_val = incremental.get(sku, 0)
        rep_val = replayed.get(sku, 0)
        if inc_val != rep_val:
            mismatches.append((sku, inc_val, rep_val))

    if mismatches:
        for sku, inc_val, rep_val in mismatches:
            print(f"MISMATCH {sku}: incremental={inc_val} replay={rep_val}")
        sys.exit(1)
    else:
        print("OK: current stock matches replay")


def cmd_summary(state_path=STATE_PATH):
    """Print a summary of the current stock state.

    Args:
        state_path: path to the state JSON file
    """
    stock = load_state(state_path)
    if not stock:
        print("No state found.")
        return

    print("Current stock levels:")
    for sku in sorted(stock.keys()):
        print(f"  {sku}: {stock[sku]}")

    total = sum(stock.values())
    print(f"  Total: {total} units across {len(stock)} SKUs")


def main():
    """Main entry point for the ledger CLI."""
    if len(sys.argv) < 2:
        print("Usage: python3 ledger.py <command> [events_path] [state_path]")
        print("Commands: replay, verify, ingest, summary")
        sys.exit(1)

    cmd = sys.argv[1]
    events_path = sys.argv[2] if len(sys.argv) > 2 else EVENTS_PATH
    state_path = sys.argv[3] if len(sys.argv) > 3 else STATE_PATH

    if cmd == "replay":
        cmd_replay(events_path, state_path)
    elif cmd == "verify":
        cmd_verify(events_path, state_path)
    elif cmd == "ingest":
        cmd_ingest(events_path, state_path)
    elif cmd == "summary":
        cmd_summary(state_path)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
