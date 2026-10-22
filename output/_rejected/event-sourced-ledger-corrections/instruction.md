The warehouse inventory ledger at /app/ tracks stock for each SKU using an event-sourced design. Events (receipts, shipments, corrections) are appended to an immutable log (/app/events.jsonl), and stock is maintained incrementally in /app/state.json.

Running `python3 /app/ledger.py verify` should confirm that the incrementally maintained stock matches a full replay of the event log, and both must be correct per the business rules. Currently verify reports mismatches for some SKUs.

Business rules:
- RECEIPT: adds the event's quantity to the SKU's stock.
- SHIPMENT: subtracts the event's quantity from the SKU's stock.
- CORRECTION: changes the effective quantity of the referenced event to the correction's quantity value. If the referenced event has been corrected before, the new correction supersedes the previous one. The stock impact of a correction follows from the change in effective quantity and the referenced event's type.
- Each unique event_id must be processed exactly once, regardless of how many times it appears in the event log.

After fixing, run `python3 /app/ledger.py replay` to rebuild state.json, then `python3 /app/ledger.py verify` must report no mismatches.
