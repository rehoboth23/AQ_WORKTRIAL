# Revenue Analytics Pipeline — Operations Guide

## Overview

The revenue analytics pipeline generates monthly revenue reports from the
transaction ledger. This document describes the **business rules** that
govern the pipeline. All pipeline components (SQL views, Python code,
configuration) must implement these rules correctly.

## Data Currency

All monetary amounts in the transaction ledger are recorded in **US Dollars
(USD)**. The `conversion_rate` in `config.yaml` under `reporting.currency`
is used to convert from the ledger currency to the reporting currency.

**When the reporting currency is USD and the ledger currency is USD, the
conversion rate must be 1.0.** A rate other than 1.0 would incorrectly
scale the monetary values.

## Transaction Eligibility

Only transactions with `status = 'completed'` are included in revenue
calculations. Pending and failed transactions are excluded.

Category rules determine whether a completed transaction is included:

| Category       | Included in Revenue |
|----------------|---------------------|
| `subscription` | Yes                 |
| `one_time`     | Yes                 |
| `internal`     | **No**              |

**Transactions without a category value (NULL) are ordinary business
transactions and must be included in revenue.** These represent transactions
that were not categorized at the time of recording but are valid business
transactions. Excluding them would undercount revenue.

## Refund Handling

The `refund_amount` column in the transactions table is nullable.

- Where `refund_amount` is not recorded (NULL), the refund is **$0.00**.
- **Net revenue must always be a numeric value.** It should never be blank,
  NULL, or empty in the report output.

## Timezone

The company operates on **US Eastern Time (UTC-5)**. All timestamps in the
database are stored in UTC. Revenue should be attributed to the **business
date** (Eastern Time) of the transaction, not the UTC date.

For example:

- A transaction at `2024-02-01 00:30:00 UTC` occurred at
  `2024-01-31 19:30:00 EST` and belongs to **January**.
- A transaction at `2024-03-01 01:00:00 UTC` occurred at
  `2024-02-29 20:00:00 EST` and belongs to **February** (2024 is a leap
  year).

In SQLite, use `date(created_at, '-5 hours')` to compute the EST date.

## Report Format

The output file `report.csv` must have the following columns:

```
month,merchant_id,gross_revenue,total_refunds,net_revenue,transaction_count
```

| Column             | Format                         |
|--------------------|--------------------------------|
| `month`            | YYYY-MM                        |
| `merchant_id`      | Merchant identifier string     |
| `gross_revenue`    | Numeric, 2 decimal places      |
| `total_refunds`    | Numeric, 2 decimal places      |
| `net_revenue`      | Numeric, 2 decimal places      |
| `transaction_count`| Integer                        |

There should be one row per unique `(month, merchant_id)` combination that
has at least one eligible transaction.
