"""Database access layer for the account service.

Provides functions for CRUD operations on accounts and balance
history, as well as configuration management via the app_config table.

All database connections use WAL mode for better concurrent read
performance and PRAGMA foreign_keys=ON for referential integrity.
"""
import sqlite3
from account_service.config import DB_PATH


def get_connection():
    """Get a database connection with row factory and recommended pragmas.

    Returns:
        A sqlite3.Connection object configured with:
        - Row factory set to sqlite3.Row for dict-like access
        - WAL journal mode for better concurrency
        - Foreign keys enabled
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_account_by_username(username):
    """Look up an account by exact username match.

    Args:
        username: The username to search for. Must match exactly,
                 including Unicode normalization form.

    Returns:
        A dict with account fields, or None if not found.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM accounts WHERE username = ?",
            (username,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_account_by_username_ci(username):
    """Look up an account by case-insensitive username match.

    Uses LOWER() for case-insensitive comparison while still
    requiring exact Unicode character match. This handles the
    case where usernames differ only in case but not in their
    Unicode representation.

    Args:
        username: The username to search for (case-insensitive).

    Returns:
        A dict with account fields, or None if not found.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM accounts WHERE LOWER(username) = LOWER(?)",
            (username,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_account_by_id(account_id):
    """Look up an account by its integer ID.

    Args:
        account_id: The primary key of the account.

    Returns:
        A dict with account fields, or None if not found.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_account(username, balance=0.0):
    """Create a new account with the given username and initial balance.

    Args:
        username: The username for the new account. Should already be
                 normalized and validated before calling this function.
        balance: The initial balance, defaulting to 0.0.

    Returns:
        The integer ID of the newly created account.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO accounts (username, balance) VALUES (?, ?)",
            (username, balance)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_balance(account_id, new_balance):
    """Update the balance for an account.

    Args:
        account_id: The ID of the account to update.
        new_balance: The new balance value.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE accounts SET balance = ? WHERE id = ?",
            (new_balance, account_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_username(account_id, new_username):
    """Update the username for an account.

    Args:
        account_id: The ID of the account to update.
        new_username: The new username value.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE accounts SET username = ? WHERE id = ?",
            (new_username, account_id)
        )
        conn.commit()
    finally:
        conn.close()


def add_balance_history(account_id, username, old_balance, new_balance, operation):
    """Add a balance history entry.

    Records a balance change with the operation type for auditing.

    Args:
        account_id: The ID of the account.
        username: The username at the time of the operation.
        old_balance: The balance before the operation.
        new_balance: The balance after the operation.
        operation: The type of operation (deposit, withdrawal, adjustment, import).
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO balance_history (account_id, username, old_balance, new_balance, operation) VALUES (?, ?, ?, ?, ?)",
            (account_id, username, old_balance, new_balance, operation)
        )
        conn.commit()
    finally:
        conn.close()


def get_balance_history(account_id):
    """Get balance history for an account, ordered by creation time.

    Args:
        account_id: The ID of the account.

    Returns:
        A list of dicts with balance history fields.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM balance_history WHERE account_id = ? ORDER BY created_at",
            (account_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_accounts():
    """Get all accounts ordered by ID.

    Returns:
        A list of dicts with account fields.
    """
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_account(account_id):
    """Delete an account by ID.

    Note: This does not cascade-delete balance_history entries.
    The caller is responsible for handling orphaned history records.

    Args:
        account_id: The ID of the account to delete.
    """
    conn = get_connection()
    try:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def delete_balance_history_by_account(account_id):
    """Delete all balance history entries for an account.

    Args:
        account_id: The ID of the account whose history to delete.
    """
    conn = get_connection()
    try:
        conn.execute("DELETE FROM balance_history WHERE account_id = ?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def reassign_balance_history(old_account_id, new_account_id, new_username=None):
    """Reassign balance history entries from one account to another.

    Used during account merging to preserve history when duplicate
    accounts are consolidated.

    Args:
        old_account_id: The account ID whose history should be moved.
        new_account_id: The account ID to receive the history.
        new_username: If provided, also update the username in history rows.
    """
    conn = get_connection()
    try:
        if new_username:
            conn.execute(
                "UPDATE balance_history SET account_id = ?, username = ? WHERE account_id = ?",
                (new_account_id, new_username, old_account_id)
            )
        else:
            conn.execute(
                "UPDATE balance_history SET account_id = ? WHERE account_id = ?",
                (new_account_id, old_account_id)
            )
        conn.commit()
    finally:
        conn.close()


def count_accounts():
    """Count the total number of accounts.

    Returns:
        The integer count of accounts.
    """
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()
        return row['cnt']
    finally:
        conn.close()


def get_total_balance():
    """Get the sum of all account balances.

    Returns:
        The total balance as a float.
    """
    conn = get_connection()
    try:
        row = conn.execute("SELECT COALESCE(SUM(balance), 0.0) as total FROM accounts").fetchone()
        return row['total']
    finally:
        conn.close()


def get_config_value(key, default=None):
    """Get a configuration value from the app_config table.

    Args:
        key: The configuration key.
        default: Default value if key is not found.

    Returns:
        The configuration value as a string, or the default.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = ?",
            (key,)
        ).fetchone()
        return row['value'] if row else default
    finally:
        conn.close()


def set_config_value(key, value):
    """Set a configuration value in the app_config table.

    Uses INSERT OR REPLACE to update existing values.

    Args:
        key: The configuration key.
        value: The value to set (will be stored as string).
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()
    finally:
        conn.close()


def get_all_config():
    """Get all configuration values from the app_config table.

    Returns:
        A dict mapping keys to values.
    """
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM app_config").fetchall()
        return {r['key']: r['value'] for r in rows}
    finally:
        conn.close()


def execute_raw(sql, params=None):
    """Execute a raw SQL statement. For administrative use only.

    Args:
        sql: The SQL statement to execute.
        params: Optional tuple of parameters.

    Returns:
        The list of rows as dicts, or empty list for non-SELECT statements.
    """
    conn = get_connection()
    try:
        if params:
            cursor = conn.execute(sql, params)
        else:
            cursor = conn.execute(sql)

        if sql.strip().upper().startswith('SELECT'):
            rows = cursor.fetchall()
            result = [dict(r) for r in rows]
            return result
        else:
            conn.commit()
            return []
    finally:
        conn.close()
