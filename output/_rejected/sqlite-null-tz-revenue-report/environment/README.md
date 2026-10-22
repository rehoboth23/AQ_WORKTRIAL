# Revenue Analytics Pipeline

Monthly revenue reporting system for transaction ledger data.

## Quick Start

```bash
python3 generate_report.py
```

## Configuration

Edit `config.yaml` to adjust:
- Database path
- Reporting currency and conversion rate
- Timezone settings

## Database

The SQLite database is at `data/ledger.db`. Views are defined in:
- `sql/views.sql` — Core eligibility and filtering views
- `sql/reporting_views.sql` — Aggregation and summary views

After modifying SQL view definitions, you must drop and recreate the views
in the database before regenerating the report.

## Output

Report is generated as `report.csv` with columns:
`month, merchant_id, gross_revenue, total_refunds, net_revenue, transaction_count`
