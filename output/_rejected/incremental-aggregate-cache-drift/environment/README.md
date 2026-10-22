# tally — Financial Analytics Aggregation System

## Overview

`tally` processes daily journal entries stored as JSONL files and produces
per-date, per-account aggregate totals stored as JSON. It supports two
rebuild modes:

- **Full rebuild** (`python3 tally.py full`): recomputes every aggregate
  from the source journal files.
- **Incremental rebuild** (`python3 tally.py incr`): detects which journal
  files changed since the last build and updates only the affected
  aggregates, using a per-partition contribution cache.

## Invariant

After any sequence of source edits and incremental rebuilds, the
aggregates produced by the incremental mode must **exactly equal** those
produced by a full rebuild. If they ever diverge, the system is
incorrect.

## Data Layout

```
/app/data/
├── journals/          Source JSONL files (journal_YYYY-MM-DD.jsonl)
├── agg/               Per-date aggregate JSON files (YYYY-MM-DD.json)
├── cache/             Per-partition contribution cache (journal_YYYY-MM-DD.json)
└── manifest.json      File hashes and build metadata
```

### Journal Entry Format

Each line in a journal JSONL file is a JSON object:

```json
{"id": "REV-001", "date": "2024-01-15", "account": "Revenue", "amount": 2500.00, "description": "Product sales"}
```

Optional fields:
- `voided`: boolean, defaults to `false`. Voided entries do not contribute to aggregates.

The `date` field may differ from the journal file name (late-arriving entries).

### Aggregate Format

Each aggregate file (`YYYY-MM-DD.json`) maps account names to numeric totals:

```json
{"Discounts": -150.00, "Payroll": 4200.00, "Refunds": -320.00, "Revenue": 4300.00}
```

## Commands

| Command   | Description                                    |
|-----------|------------------------------------------------|
| `full`    | Full rebuild from all journals                 |
| `incr`    | Incremental rebuild for changed files          |
| `report`  | Volume report (absolute values)                |
| `summary` | Data summary with grand totals                 |
| `export`  | Export aggregates as CSV                       |
| `check`   | Validate journal file integrity                |
| `verify`  | Verify aggregates match source computation     |
| `cache`   | Show cache contents for a partition            |
| `health`  | Check cache files for issues                   |
| `rollup`  | Group-level rollup report                      |
| `reconcile` | Reconcile one date against source            |

## Accounts

Standard accounts and their classification:

| Account    | Type          | Group      |
|------------|---------------|------------|
| Revenue    | income        | operating  |
| Services   | income        | operating  |
| Consulting | income        | operating  |
| Refunds    | contra_income | operating  |
| Discounts  | contra_income | operating  |
| Payroll    | expense       | operating  |
| Rent       | expense       | facility   |
| Supplies   | expense       | admin      |
