# Payment Webhook Consumer

Processes payment delivery notifications from PayStream, a payment
provider that retries failed deliveries.

## Overview

PayStream sends delivery notifications when payment events occur. If a
delivery fails (network error, timeout, server error, etc.), PayStream
retries it with a **new delivery_id** but the **same event_id**. The
consumer must ensure each unique event affects account balances exactly
once, regardless of how many delivery attempts arrive.

## CLI Usage

```
python3 /app/cli.py init                                        # Initialize schema
python3 /app/cli.py receive DEL123 EVT456 ACC001 150.00         # Receive a delivery
python3 /app/cli.py process                                     # Process pending deliveries
python3 /app/cli.py reconcile                                   # Verify balances
```

### Commands

| Command    | Description                                      |
|------------|--------------------------------------------------|
| `init`     | Create database tables (idempotent)              |
| `receive`  | Accept a delivery notification into the queue     |
| `process`  | Apply all pending deliveries to account balances  |
| `reconcile`| Compare actual balances to expected values        |

### receive arguments

| Argument     | Meaning                                        |
|--------------|------------------------------------------------|
| `delivery_id`| Unique identifier for this delivery attempt     |
| `event_id`   | Logical event identifier (shared across retries)|
| `account_id` | Target account                                  |
| `amount`     | Payment amount (negative for refunds)           |

## Database

Location: `/app/data/payments.db` (SQLite, WAL journal mode).

### Schema

**accounts**

| Column           | Type    | Description                    |
|------------------|---------|--------------------------------|
| account_id (PK)  | TEXT    | Account identifier             |
| name             | TEXT    | Account holder name            |
| balance          | REAL    | Current balance                |
| initial_balance  | REAL    | Balance before any events      |

**deliveries**

| Column           | Type    | Description                              |
|------------------|---------|------------------------------------------|
| delivery_id (PK) | TEXT    | Unique delivery attempt identifier       |
| event_id         | TEXT    | Logical event (shared by retries)        |
| account_id       | TEXT    | Target account                           |
| amount           | REAL    | Payment amount (negative = refund)       |
| status           | TEXT    | 'pending' or 'processed'                 |
| received_at      | TEXT    | Timestamp when delivery was received     |

**processed_events**

| Column           | Type    | Description                              |
|------------------|---------|------------------------------------------|
| event_id (PK)    | TEXT    | Event that has been fully processed      |
| processed_at     | TEXT    | Timestamp when event was recorded        |

### Delivery Lifecycle

1. A delivery arrives via `receive` and is inserted with status
   `'pending'`.
2. The processor picks up pending deliveries, applies the balance
   change, records the event in `processed_events`, and marks the
   delivery as `'processed'`.

## Idempotency

Each unique event_id must affect each account's balance at most once.
The system uses event-level deduplication (via `processed_events`) to
prevent double-counting when PayStream retries a delivery or when the
processor is restarted after an interruption.
