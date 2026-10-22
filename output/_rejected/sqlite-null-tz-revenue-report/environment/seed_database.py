#!/usr/bin/env python3
"""Seed the ledger database with transaction data.

This script creates the SQLite database with transaction and category_rules
tables, populates them with deterministic data, and creates the SQL views.
It is deleted after the Docker image is built.
"""

import sqlite3
import os
import random

DB_PATH = "data/ledger.db"


def main():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)

    # Create tables
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            merchant_id TEXT NOT NULL,
            amount REAL NOT NULL,
            refund_amount REAL,
            category TEXT,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS category_rules (
            category TEXT PRIMARY KEY,
            include_in_revenue INTEGER NOT NULL
        )
    """
    )

    # Insert category rules (no entry for NULL — NULL categories are
    # handled by the view logic, not by a lookup row)
    conn.executemany(
        "INSERT INTO category_rules VALUES (?, ?)",
        [
            ("internal", 0),
            ("subscription", 1),
            ("one_time", 1),
        ],
    )
    conn.commit()

    # Generate deterministic transactions
    rng = random.Random(42)
    merchants = ["M001", "M002", "M003", "M004"]
    categories_weighted = [
        ("subscription", 0.40),
        ("one_time", 0.35),
        ("internal", 0.10),
        (None, 0.15),
    ]
    cat_choices = [c[0] for c in categories_weighted]
    cat_weights = [c[1] for c in categories_weighted]

    tx_id = 1
    transactions = []
    days_in_month = {1: 31, 2: 29, 3: 31}

    for month in [1, 2, 3]:
        for day in range(1, days_in_month[month] + 1):
            num_tx = rng.randint(1, 2)
            for _ in range(num_tx):
                merchant = rng.choice(merchants)
                category = rng.choices(cat_choices, weights=cat_weights, k=1)[0]
                amount = round(rng.uniform(10, 500), 2)

                if rng.random() < 0.65:
                    refund_amount = None
                else:
                    refund_amount = round(rng.uniform(1, amount * 0.3), 2)

                r = rng.random()
                if r < 0.85:
                    status = "completed"
                elif r < 0.95:
                    status = "pending"
                else:
                    status = "failed"

                hour = rng.randint(0, 23)
                minute = rng.randint(0, 59)
                second = rng.randint(0, 59)
                created_at = (
                    f"2024-{month:02d}-{day:02d} "
                    f"{hour:02d}:{minute:02d}:{second:02d}"
                )

                transactions.append(
                    (tx_id, merchant, amount, refund_amount, category, status, created_at)
                )
                tx_id += 1

    # Add specific boundary-crossing transactions for testing
    # 2024-02-01 00:30 UTC → EST Jan 31 → belongs to January
    transactions.append(
        (tx_id, "M001", 150.00, None, "subscription", "completed", "2024-02-01 00:30:00")
    )
    tx_id += 1

    # 2024-03-01 01:00 UTC → EST Feb 29 → belongs to February (leap year)
    transactions.append(
        (tx_id, "M002", 200.00, 15.00, "one_time", "completed", "2024-03-01 01:00:00")
    )
    tx_id += 1

    # Additional NULL-category transactions to ensure they are significant
    for m in [1, 2, 3]:
        for i in range(3):
            day = rng.randint(1, days_in_month[m])
            hour = rng.randint(5, 20)
            merchant = rng.choice(merchants)
            amount = round(rng.uniform(20, 300), 2)
            created_at = (
                f"2024-{m:02d}-{day:02d} "
                f"{hour:02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"
            )
            transactions.append(
                (tx_id, merchant, amount, None, None, "completed", created_at)
            )
            tx_id += 1

    # Insert all transactions
    conn.executemany(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)", transactions
    )
    conn.commit()

    # Ensure M003 February has ALL NULL refund_amounts for completed
    # non-internal transactions — this guarantees the NULL propagation
    # bug is visible in the report (blank net_revenue for that row)
    conn.execute(
        """
        UPDATE transactions SET refund_amount = NULL
        WHERE merchant_id = 'M003'
          AND status = 'completed'
          AND strftime('%Y-%m', created_at) = '2024-02'
          AND (category IS NULL OR category != 'internal')
    """
    )
    conn.commit()

    # Create views from SQL files (the buggy versions)
    for sql_file in ["sql/views.sql", "sql/reporting_views.sql"]:
        with open(sql_file, "r") as f:
            sql = f.read()
        conn.executescript(sql)

    conn.commit()
    conn.close()
    print(f"Database seeded with {len(transactions)} transactions")


if __name__ == "__main__":
    main()
