#!/usr/bin/env python3
"""Build-time script to initialize the payments database with sample data.

Creates 5 accounts and 11 delivery notifications (8 unique events
plus 3 retries that share event_ids with originals). All deliveries
start in 'pending' status.

This script is deleted from the image after the database is created.
"""

import sqlite3
import os

DB_PATH = "/app/data/payments.db"

SCHEMA = """
    CREATE TABLE IF NOT EXISTS accounts (
        account_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0,
        initial_balance REAL NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS deliveries (
        delivery_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        received_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS processed_events (
        event_id TEXT PRIMARY KEY,
        processed_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_deliveries_event_id
        ON deliveries(event_id);
    CREATE INDEX IF NOT EXISTS idx_deliveries_status
        ON deliveries(status);
    CREATE INDEX IF NOT EXISTS idx_deliveries_account_id
        ON deliveries(account_id);
"""


def setup():
    """Create the database and populate it with sample data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    # --- Sample accounts ---
    accounts = [
        ("ACC001", "Alice Merchants",  1000.00, 1000.00),
        ("ACC002", "Bob's Bakery",      500.00,  500.00),
        ("ACC003", "Charlie Corp",     2500.00, 2500.00),
        ("ACC004", "Diana Designs",       0.00,    0.00),
        ("ACC005", "Eve Electronics",   750.00,  750.00),
    ]
    conn.executemany(
        "INSERT INTO accounts (account_id, name, balance, initial_balance) "
        "VALUES (?, ?, ?, ?)",
        accounts,
    )

    # --- Sample deliveries (8 unique events + 3 retries = 11 rows) ---
    # PayStream retries get a new delivery_id but carry the same event_id.
    deliveries = [
        # Original deliveries
        ("DEL001", "EVT001", "ACC001",  150.00),  # charge – Alice
        ("DEL002", "EVT002", "ACC002",  200.00),  # charge – Bob
        ("DEL003", "EVT003", "ACC001",  -50.00),  # refund – Alice
        ("DEL004", "EVT004", "ACC003",  300.00),  # charge – Charlie
        ("DEL005", "EVT005", "ACC004",  100.00),  # charge – Diana (zero-balance acct)
        ("DEL007", "EVT006", "ACC005",  175.00),  # charge – Eve
        ("DEL008", "EVT007", "ACC001",  250.00),  # charge – Alice
        ("DEL010", "EVT008", "ACC003",  450.00),  # charge – Charlie
        # Retries (same event_id, different delivery_id)
        ("DEL006", "EVT002", "ACC002",  200.00),  # retry of EVT002 – Bob
        ("DEL009", "EVT004", "ACC003",  300.00),  # retry of EVT004 – Charlie
        ("DEL011", "EVT005", "ACC004",  100.00),  # retry of EVT005 – Diana
    ]
    conn.executemany(
        "INSERT INTO deliveries "
        "(delivery_id, event_id, account_id, amount, status, received_at) "
        "VALUES (?, ?, ?, ?, 'pending', datetime('now'))",
        deliveries,
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    setup()
