"""SQLite storage layer for LinkVault."""

import sqlite3
import os
import hashlib

DB_PATH = '/app/data/linkvault.db'


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS links (
        code TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        username TEXT NOT NULL
    )''')
    # Seed admin user
    pw_hash = hashlib.sha256('admin123'.encode()).hexdigest()
    conn.execute(
        'INSERT OR IGNORE INTO users (username, password_hash, display_name) VALUES (?, ?, ?)',
        ('admin', pw_hash, 'Administrator')
    )
    # Seed sample short links
    conn.execute(
        "INSERT OR IGNORE INTO links (code, url, created_by) VALUES (?, ?, ?)",
        ('abc123', 'https://example.com', 'admin')
    )
    conn.execute(
        "INSERT OR IGNORE INTO links (code, url, created_by) VALUES (?, ?, ?)",
        ('xyz789', 'https://python.org', 'admin')
    )
    conn.commit()
    conn.close()


def get_link(code):
    conn = get_connection()
    row = conn.execute('SELECT url FROM links WHERE code = ?', (code,)).fetchone()
    conn.close()
    return row['url'] if row else None


def create_link(code, url, created_by=None):
    conn = get_connection()
    conn.execute(
        'INSERT INTO links (code, url, created_by) VALUES (?, ?, ?)',
        (code, url, created_by)
    )
    conn.commit()
    conn.close()


def get_user(username):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_display_name(username, display_name):
    conn = get_connection()
    conn.execute(
        'UPDATE users SET display_name = ? WHERE username = ?',
        (display_name, username)
    )
    conn.commit()
    conn.close()


def get_display_name(username):
    conn = get_connection()
    row = conn.execute('SELECT display_name FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row['display_name'] if row else None


def create_session(username):
    import uuid
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        'INSERT INTO sessions (session_id, username) VALUES (?, ?)',
        (session_id, username)
    )
    conn.commit()
    conn.close()
    return session_id


def get_session_user(session_id):
    conn = get_connection()
    row = conn.execute('SELECT username FROM sessions WHERE session_id = ?', (session_id,)).fetchone()
    conn.close()
    return row['username'] if row else None
