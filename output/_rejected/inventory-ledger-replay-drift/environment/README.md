# Inventory Ledger

Event-sourced inventory tracking system for warehouse stock management.

## Overview

The ledger records `RECEIVE`, `SHIP`, `RETURN`, and `CORRECT` events in an
append-only JSONL log and maintains a materialised stock snapshot. It supports:

- **Late corrections** — Adjust a past event's quantity after the fact
  (e.g., a shipment count that was misreported).
- **Idempotent processing** — If the same event is delivered more than once due
  to message redelivery, it is applied exactly once.

## Data Files

All data lives in `/app/data/`:

| File            | Description                                   |
|-----------------|-----------------------------------------------|
| `events.jsonl`  | Append-only event log (one JSON object/line)  |
| `snapshot.json` | Current stock levels `{sku: quantity}`        |
| `applied.json`  | Set of applied event IDs `{event_id: true}`   |

## Commands

```
python3 /app/ledger.py <command> [args...]
```

| Command                            | Description                              |
|------------------------------------|------------------------------------------|
| `receive <sku> <qty> [event_id]`   | Record items received                    |
| `ship <sku> <qty> [event_id]`      | Record items shipped                     |
| `return <sku> <qty> [event_id]`    | Record items returned                    |
| `correct <ref_id> <new_qty> [eid]` | Correct a past event's effective qty     |
| `rebuild`                          | Deduplicate log & rebuild snapshot       |
| `show`                             | Display current stock levels             |
| `verify`                           | Check snapshot against full event replay |
| `history`                          | Show event log (human-readable)          |
| `log`                              | Dump raw event log (JSON lines)          |

## Event Types

- **RECEIVE** `sku qty` — Items arrived at the warehouse.
- **SHIP** `sku qty` — Items left the warehouse.
- **RETURN** `sku qty` — Items returned to the warehouse.
- **CORRECT** `ref_id new_qty` — A past event's quantity was different from
  what was originally recorded. The correction adjusts stock accordingly.

## Idempotency

Events may be redelivered by the messaging system. The ledger tracks which
event IDs have been applied in `applied.json`. Processing an event whose ID
is already in the applied set has no effect on stock.

## Corrections

A `CORRECT` event adjusts stock because a past event's quantity was different
from what was originally recorded. For example, if a `RECEIVE` was recorded
as 100 units but only 80 actually arrived, a correction with `new_qty=80`
reduces stock by 20.

The sign of the adjustment depends on the referenced event's type: SHIP
events have inverted sign because more shipped means less stock.

## Reconciliation

- **verify** — Replays the entire event log from scratch and compares the
  result against the live snapshot. Reports any discrepancies.
- **rebuild** — Removes duplicate entries from the event log and rebuilds
  both the snapshot and the applied set from a clean replay. Use this when
  the log has been corrupted (e.g., by duplicate entries from redeliveries).

## Consistency

After any sequence of operations, the snapshot must match a full replay of
the event log, and the log must contain exactly one entry for each distinct
event.
