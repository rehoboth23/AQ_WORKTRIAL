# Fix the Nightly ETL Job

A company's nightly ETL job loads the day's CSV exports from `/data/imports/` into a local PostgreSQL 15 database and publishes a summary report at `/data/reports/daily_summary.txt`.

After a recent crash and some system changes, the job no longer completes successfully.

## Your Task

Fix the environment and any issues so that running:

```
python3 /app/etl_runner.py
```

from a clean state completes without error and produces a correct report at `/data/reports/daily_summary.txt`.

## Database

| Setting | Value |
|---------|-------|
| Host    | localhost |
| Port    | 5432 |
| Database | etl_db |
| User    | etl_user |
| Password | etl_pass |

## Business Rules for the Report

The daily summary report must follow these rules:

1. **Completed orders only**: Revenue and order counts include only orders with `status='completed'`. Cancelled orders are excluded from ALL totals and breakdowns.

2. **Regional breakdown**: Regions listed alphabetically by name.

3. **Top products**: Sorted by revenue descending, then product name ascending for ties.

4. **Currency formatting**: All monetary amounts use a dollar sign, comma thousands separator, and exactly two decimal places (e.g. `$1,234.56`).

## End State

When you are done:

- `python3 /app/etl_runner.py` completes with exit code 0 and no errors on stderr.
- The file `/data/reports/daily_summary.txt` exists and is a regular file (not a directory or special file).
- The report follows all business rules above.
