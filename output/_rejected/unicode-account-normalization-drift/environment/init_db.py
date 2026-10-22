"""Initialize the accounts database with schema and sample data.

This script creates the SQLite database at /app/data/accounts.db,
sets up the schema (accounts, balance_history, app_config tables),
and populates it with initial data.

Run once during Docker image build. Deleted after database creation.
"""
import sqlite3
import unicodedata
import os
from datetime import datetime, timezone

DB_PATH = '/app/data/accounts.db'


def init_db():
    """Initialize the database with schema and sample data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            balance REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            old_balance REAL NOT NULL,
            new_balance REAL NOT NULL,
            operation TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts(username);
        CREATE INDEX IF NOT EXISTS idx_balance_history_account ON balance_history(account_id);
        CREATE INDEX IF NOT EXISTS idx_balance_history_created ON balance_history(created_at);
    """)

    # Insert app_config settings
    conn.executemany(
        "INSERT INTO app_config (key, value) VALUES (?, ?)",
        [
            ('normalization_form', 'NFD'),
            ('max_username_length', '64'),
            ('min_balance', '-1000.0'),
            ('max_balance', '999999999.0'),
        ]
    )

    # ASCII accounts
    ascii_accounts = [
        ('alice', 1000.0, '2024-01-15T10:00:00+00:00'),
        ('bob', 750.0, '2024-02-01T14:30:00+00:00'),
        ('charlie', 250.0, '2024-03-10T09:15:00+00:00'),
        ('diana', 1200.0, '2024-04-05T16:45:00+00:00'),
        ('eve', 0.0, '2024-05-20T11:00:00+00:00'),
        ('frank', 450.0, '2024-06-12T08:30:00+00:00'),
        ('grace', 890.0, '2024-07-18T13:20:00+00:00'),
        ('henry', 320.0, '2024-08-22T15:45:00+00:00'),
    ]

    # Unicode accounts with composed accented characters
    nfc_accounts = [
        (unicodedata.normalize('NFC', 'café'), 500.0, '2024-06-01T08:00:00+00:00'),
        (unicodedata.normalize('NFC', 'naïve'), 200.0, '2024-06-15T12:30:00+00:00'),
        (unicodedata.normalize('NFC', 'björk'), 150.0, '2024-07-01T10:00:00+00:00'),
        (unicodedata.normalize('NFC', 'straße'), 350.0, '2024-07-10T15:00:00+00:00'),
        (unicodedata.normalize('NFC', 'rené'), 100.0, '2024-08-01T09:00:00+00:00'),
        (unicodedata.normalize('NFC', 'søren'), 75.0, '2024-08-15T11:30:00+00:00'),
        (unicodedata.normalize('NFC', 'josé'), 220.0, '2024-09-01T14:00:00+00:00'),
        (unicodedata.normalize('NFC', 'françois'), 180.0, '2024-09-15T16:00:00+00:00'),
    ]

    # Unicode accounts with decomposed accented characters
    nfd_accounts = [
        (unicodedata.normalize('NFD', 'café'), 300.0, '2024-05-15T07:00:00+00:00'),
        (unicodedata.normalize('NFD', 'andersen'), 50.0, '2024-10-01T08:30:00+00:00'),
        (unicodedata.normalize('NFD', 'über'), 125.0, '2024-10-15T10:00:00+00:00'),
        (unicodedata.normalize('NFD', 'müller'), 275.0, '2024-11-01T12:30:00+00:00'),
    ]

    # café appears in both lists above with different internal representations

    all_accounts = ascii_accounts + nfc_accounts + nfd_accounts

    for username, balance, created_at in all_accounts:
        cursor = conn.execute(
            "INSERT INTO accounts (username, balance, created_at) VALUES (?, ?, ?)",
            (username, balance, created_at)
        )
        account_id = cursor.lastrowid

        # Add initial balance history entry for accounts with non-zero balance
        if balance > 0:
            conn.execute(
                "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (account_id, username, 0.0, balance, 'initial', created_at)
            )

    # Add additional balance history entries for testing

    # Alice had a deposit when she first signed up
    alice_row = conn.execute("SELECT id FROM accounts WHERE username = 'alice'").fetchone()
    if alice_row:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (alice_row['id'], 'alice', 0.0, 1000.0, 'deposit', '2024-01-15T10:00:00+00:00')
        )

    # Bob had an initial deposit then a withdrawal
    bob_row = conn.execute("SELECT id FROM accounts WHERE username = 'bob'").fetchone()
    if bob_row:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (bob_row['id'], 'bob', 0.0, 1000.0, 'deposit', '2024-02-01T14:30:00+00:00')
        )
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (bob_row['id'], 'bob', 1000.0, 750.0, 'withdrawal', '2024-02-05T10:00:00+00:00')
        )

    # Get café account IDs for balance history
    cafe_nfc_username = unicodedata.normalize('NFC', 'café')
    cafe_nfd_username = unicodedata.normalize('NFD', 'café')

    cafe_nfc = conn.execute(
        "SELECT id FROM accounts WHERE username = ?",
        (cafe_nfc_username,)
    ).fetchone()

    cafe_nfd = conn.execute(
        "SELECT id FROM accounts WHERE username = ?",
        (cafe_nfd_username,)
    ).fetchone()

    # Add balance history for both café accounts
    if cafe_nfc:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cafe_nfc['id'], cafe_nfc_username, 0.0, 500.0, 'deposit', '2024-06-01T08:00:00+00:00')
        )

    if cafe_nfd:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cafe_nfd['id'], cafe_nfd_username, 0.0, 300.0, 'deposit', '2024-05-15T07:00:00+00:00')
        )

    # Add some history for NFC naïve
    naive_nfc_username = unicodedata.normalize('NFC', 'naïve')
    naive_nfc = conn.execute(
        "SELECT id FROM accounts WHERE username = ?",
        (naive_nfc_username,)
    ).fetchone()
    if naive_nfc:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (naive_nfc['id'], naive_nfc_username, 0.0, 200.0, 'deposit', '2024-06-15T12:30:00+00:00')
        )

    # Add history for NFC björk
    bjork_nfc_username = unicodedata.normalize('NFC', 'björk')
    bjork_nfc = conn.execute(
        "SELECT id FROM accounts WHERE username = ?",
        (bjork_nfc_username,)
    ).fetchone()
    if bjork_nfc:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (bjork_nfc['id'], bjork_nfc_username, 0.0, 150.0, 'deposit', '2024-07-01T10:00:00+00:00')
        )

    # Add history for NFD über
    uber_nfd_username = unicodedata.normalize('NFD', 'über')
    uber_nfd = conn.execute(
        "SELECT id FROM accounts WHERE username = ?",
        (uber_nfd_username,)
    ).fetchone()
    if uber_nfd:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (uber_nfd['id'], uber_nfd_username, 0.0, 125.0, 'deposit', '2024-10-15T10:00:00+00:00')
        )

    # Add history for NFD müller
    muller_nfd_username = unicodedata.normalize('NFD', 'müller')
    muller_nfd = conn.execute(
        "SELECT id FROM accounts WHERE username = ?",
        (muller_nfd_username,)
    ).fetchone()
    if muller_nfd:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (muller_nfd['id'], muller_nfd_username, 0.0, 275.0, 'deposit', '2024-11-01T12:30:00+00:00')
        )

    conn.commit()
    conn.close()

    print(f"Database initialized at {DB_PATH}")

    # Verify data
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    print(f"Total accounts: {count}")

    # Show the café duplicate
    cafe_rows = conn.execute(
        "SELECT id, username, balance, hex(username) FROM accounts WHERE username LIKE 'caf%'"
    ).fetchall()
    for row in cafe_rows:
        print(f"  ID={row[0]}, username={row[1]}, balance={row[2]}, hex={row[3]}")

    # Show config
    config_rows = conn.execute("SELECT key, value FROM app_config").fetchall()
    for row in config_rows:
        print(f"  Config: {row[0]}={row[1]}")

    conn.close()


if __name__ == '__main__':
    init_db()
