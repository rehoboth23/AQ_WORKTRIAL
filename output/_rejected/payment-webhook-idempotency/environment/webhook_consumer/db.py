"""Database connection management and schema initialization."""

import sqlite3
import os
from config import DB_PATH


def get_connection(db_path=None):
    """Return a connection to the payments database.

    Args:
        db_path: Optional path override. Defaults to config.DB_PATH.

    Returns:
        sqlite3.Connection with WAL journal mode and row factory enabled.
    """
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Create database tables if they do not already exist.

    Idempotent — safe to call on every startup.

    Schema:
        accounts(account_id, name, balance, initial_balance)
        deliveries(delivery_id, event_id, account_id, amount, status, received_at)
        processed_events(event_id, processed_at)
    """
    conn.executescript("""
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
    """)
    conn.commit()
