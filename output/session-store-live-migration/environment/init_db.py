#!/usr/bin/env python3
"""Populate /app/data/sessions.db with 20 initial sessions at build time."""

import json
import os
import sqlite3
import uuid

DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "sessions.db")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            ttl        INTEGER NOT NULL,
            expires_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )

    rows = []
    for i in range(20):
        sid = str(uuid.uuid4())
        # 10 long-TTL, 5 medium-TTL, 5 short-TTL
        if i < 10:
            ttl = 300
        elif i < 15:
            ttl = 5
        else:
            ttl = 2
        data = {"user": f"user{i}", "counter": i, "batch": "initial"}
        # Use a fixed epoch so the build is reproducible.
        # Sessions are created "now" relative to build; short-TTL ones
        # will expire quickly, which exercises the copy-skip-expired rule.
        base_ts = 1700000000.0
        updated_at = base_ts
        expires_at = base_ts + ttl
        rows.append(
            (sid, json.dumps(data), ttl, expires_at, updated_at)
        )

    conn.executemany(
        "INSERT INTO sessions "
        "(session_id, data, ttl, expires_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Initialised {len(rows)} sessions in {DB_PATH}")


if __name__ == "__main__":
    main()
