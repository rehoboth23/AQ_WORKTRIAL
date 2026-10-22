# Warehouse Inventory Ledger

An event-sourced inventory ledger that tracks stock for each SKU in
a warehouse system.

## Overview

Events (receipts, shipments, corrections) are appended to an immutable
log file (`events.jsonl`). Stock levels are maintained incrementally
in a state file (`state.json`). A verification command compares the
incremental state against a full replay of the event log to detect
any divergence.

## Event Types

- **RECEIPT**: Adds the event's quantity to the SKU's stock.
- **SHIPMENT**: Subtracts the event's quantity from the SKU's stock.
- **CORRECTION**: Changes the effective quantity of the referenced
  event to the correction's `quantity` value. If the referenced event
  has been corrected before, the new correction supersedes the
  previous one. The stock impact of a correction follows from the
  change in effective quantity and the referenced event's type.

## Event Format

Each event in `events.jsonl` is a JSON object on a single line:

| Field      | Description                                                 |
|------------|-------------------------------------------------------------|
| `id`       | Per-line sequence number in the JSONL file                  |
| `event_id` | Logical event identifier (shared by redeliveries)           |
| `type`     | One of `RECEIPT`, `SHIPMENT`, `CORRECTION`                  |
| `sku`      | The SKU affected                                            |
| `quantity` | The quantity (for CORRECTION, the new effective quantity)   |
| `ref_id`   | For CORRECTION only: the `event_id` of the event to correct |

## Deduplication

Each unique `event_id` must be processed exactly once, regardless of
how many times it appears in the event log. Events with the same
`event_id` but different `id` values are redeliveries and should be
skipped on second and subsequent appearances.

## Commands

```bash
# Replay the entire event log and save result as new state
python3 ledger.py replay

# Rebuild state by incrementally re-processing all events
python3 ledger.py ingest

# Verify incremental state matches a full replay
python3 ledger.py verify

# Print a summary of current stock levels
python3 ledger.py summary
```

## Consistency

The `verify` command compares the incrementally maintained stock
against a full replay of the event log, reporting any SKU where
the two computation paths produce different values.
