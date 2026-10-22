import sqlite3
from docvault.config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS docs (
            title TEXT PRIMARY KEY,
            author TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS shortcuts (
            code TEXT PRIMARY KEY,
            url TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prefs (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    ''')
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO shortcuts (code, url) VALUES (?, ?)",
        ('home', '/dashboard')
    )
    cur.execute(
        "INSERT OR IGNORE INTO docs (title, author, content) VALUES (?, ?, ?)",
        ('Welcome', 'admin', 'Welcome to DocVault, your internal document management service.')
    )
    cur.execute(
        "INSERT OR IGNORE INTO prefs (key, value) VALUES (?, ?)",
        ('layout', 'default')
    )
    conn.commit()
    conn.close()


def create_doc(title, author, content):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO docs (title, author, content) VALUES (?, ?, ?)",
        (title, author, content)
    )
    conn.commit()
    conn.close()


def list_docs():
    conn = get_conn()
    rows = conn.execute("SELECT title, author FROM docs").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_doc(title):
    conn = get_conn()
    row = conn.execute(
        "SELECT title, author, content FROM docs WHERE title = ?",
        (title,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_shortcut(code):
    conn = get_conn()
    row = conn.execute(
        "SELECT url FROM shortcuts WHERE code = ?",
        (code,)
    ).fetchone()
    conn.close()
    return row['url'] if row else None


def create_shortcut(code, url):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO shortcuts (code, url) VALUES (?, ?)",
        (code, url)
    )
    conn.commit()
    conn.close()


def set_pref(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO prefs (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_pref(key):
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM prefs WHERE key = ?",
        (key,)
    ).fetchone()
    conn.close()
    return row['value'] if row else None
