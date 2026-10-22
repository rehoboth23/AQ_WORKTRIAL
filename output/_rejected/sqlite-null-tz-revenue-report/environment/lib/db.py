"""Database connection management for the revenue analytics pipeline.

Provides connection handling for the SQLite database that stores
the transaction ledger and reporting views.
"""

import sqlite3
from lib.constants import DEFAULT_DB_PATH


def get_connection(config=None):
    """Get a database connection with row factory enabled.

    Args:
        config: Optional configuration dictionary. If provided,
                the database path is read from config.database.path.

    Returns:
        sqlite3.Connection with Row factory set for dict-like access.
    """
    if config:
        db_path = config.get("database", {}).get("path", DEFAULT_DB_PATH)
    else:
        db_path = DEFAULT_DB_PATH

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(conn, sql, params=None):
    """Execute a query and return all results.

    Args:
        conn: Active database connection.
        sql: SQL query string.
        params: Optional query parameters.

    Returns:
        List of Row objects.
    """
    if params:
        cursor = conn.execute(sql, params)
    else:
        cursor = conn.execute(sql)
    return cursor.fetchall()


def execute_sql_file(conn, filepath):
    """Execute all SQL statements from a file.

    Useful for (re)creating views or running migration scripts.

    Args:
        conn: Active database connection.
        filepath: Path to the SQL file.
    """
    with open(filepath, "r") as f:
        sql = f.read()
    conn.executescript(sql)


def list_views(conn):
    """List all views in the database.

    Args:
        conn: Active database connection.

    Returns:
        List of view names.
    """
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    )
    return [row["name"] for row in cursor]
