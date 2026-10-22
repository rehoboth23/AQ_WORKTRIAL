# ETL Runner

Nightly ETL job that loads CSV exports from `/data/imports/` into a local
PostgreSQL database and generates a summary report at
`/data/reports/daily_summary.txt`.

## Quick Start

```bash
python3 /app/etl_runner.py
```

## Configuration

| Setting | Value |
|---------|-------|
| Database host | localhost |
| Database port | 5432 |
| Database name | etl_db |
| Database user | etl_user |
| Database password | etl_pass |

## Data Files

CSV files in `/data/imports/`:

- `customers.csv` — columns: customer_id, name, region
- `products.csv` — columns: product_id, name, price
- `orders.csv` — columns: order_id, customer_id, product_id, quantity, unit_price, status

## Report

The daily summary report includes:

- Total completed orders and revenue
- Regional breakdown (alphabetical by region name)
- Top products sorted by revenue descending, then product name ascending
  for ties

All monetary amounts are formatted as USD with a dollar sign, comma
thousands separator, and exactly two decimal places (e.g. `$1,234.56`).

## How It Works

1. Acquires a lock file to prevent concurrent runs.
2. Connects to PostgreSQL and creates the schema (if needed).
3. Checks an import manifest to skip already-loaded files.
4. Bulk-loads CSV data using server-side `COPY FROM`.
5. Generates the summary report using the queries in `db/queries.sql`.
6. Writes the report to `/data/reports/daily_summary.txt`.
