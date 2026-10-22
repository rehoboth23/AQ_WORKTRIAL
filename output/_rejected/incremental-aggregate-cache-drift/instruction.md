The `tally` system at `/app/tally.py` produces daily financial aggregates from journal entries in `/app/data/journals/`, writing results to `/app/data/agg/`.

Two modes are available:
- `python3 /app/tally.py full` — full rebuild from all source journals
- `python3 /app/tally.py incr` — incremental update for changed files only, using a per-partition contribution cache

After editing journal entries and running incremental rebuilds, the daily totals drift from what a fresh full rebuild produces. Some accounts show incorrect values, and discrepancies compound across successive incremental runs.

The system must guarantee: **after any sequence of source edits and incremental rebuilds, the aggregates from `incr` must exactly equal those from `full`.** Both modes must work and the output format (per-date JSON files mapping account names to numeric amounts) must not change.

Journal files are JSONL (one JSON object per line) with fields `id`, `date`, `account`, `amount`, `description`, and optional `voided` (boolean, defaults to false). A file's name is its collection date, but entries may carry different `date` values (late-arriving entries). Voided entries do not contribute.

Fix the system so the invariant holds.
