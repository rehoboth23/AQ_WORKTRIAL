#!/usr/bin/env python3
"""Create the warehouse inventory database for audit export testing.

Generates a SQLite database with ~217 inventory transactions across 5
warehouses (ALPHA, BETA, CENTRAL, DELTA, GAMMA) over January 2024.

Transactions are inserted in reverse alphabetical warehouse order so that
auto-incremented IDs diverge from the (warehouse_id, tx_date, id) sort
order: GAMMA gets the lowest IDs and ALPHA the highest, but the export
sorts ALPHA first.
"""

import sqlite3
import os
import random

DB_PATH = '/app/warehouse.db'

WAREHOUSES = ['ALPHA', 'BETA', 'CENTRAL', 'DELTA', 'GAMMA']

IN_DESCRIPTIONS = [
    'Received from supplier',
    'Stock replenishment',
    'Transfer in from {}',
    'Return from customer',
    'Adjustment IN',
    'Seasonal stock receipt',
    'Consignment received',
    'Emergency restock',
    'Quality check passed',
    'Repackaged items',
    'Vendor delivery',
    'Inter-warehouse transfer in',
]

OUT_DESCRIPTIONS = [
    'Shipped to customer',
    'Transfer out to {}',
    'Damaged goods write-off',
    'Adjustment OUT',
    'Seasonal clearance',
    'Return to supplier',
    'Recalled items',
    'Expired stock removal',
    'Customer pickup',
    'Warehouse redistribution',
    'Inter-warehouse transfer out',
    'Scrapped inventory',
]


def create_database():
    """Create and populate the warehouse database."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id TEXT NOT NULL,
            tx_date TEXT NOT NULL,
            tx_type TEXT NOT NULL CHECK(tx_type IN ('IN', 'OUT')),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            description TEXT NOT NULL
        )
    ''')

    cur.execute(
        'CREATE INDEX idx_tx_sort ON transactions(warehouse_id, tx_date, id)'
    )

    # Use a fixed seed so the database is deterministic across builds
    random.seed(2024)

    # Insert in reverse alphabetical order so auto-increment IDs diverge
    # from the (warehouse_id, tx_date, id) sort order.
    # When the export sorts by (warehouse_id, tx_date, id) the first
    # records belong to ALPHA, but ALPHA has the *highest* numeric IDs.
    insert_order = ['GAMMA', 'DELTA', 'CENTRAL', 'BETA', 'ALPHA']

    total = 0
    for wh in insert_order:
        # Each warehouse gets 40-48 transactions
        n = random.randint(40, 48)
        for _ in range(n):
            day = random.randint(1, 31)
            tx_date = f'2024-01-{day:02d}'

            # Slightly bias toward IN to keep balances generally positive
            if random.random() < 0.55:
                tx_type = 'IN'
                quantity = random.randint(50, 500)
                tmpl = random.choice(IN_DESCRIPTIONS)
            else:
                tx_type = 'OUT'
                quantity = random.randint(20, 300)
                tmpl = random.choice(OUT_DESCRIPTIONS)

            # Fill in a cross-warehouse reference if the template has {}
            others = [w for w in WAREHOUSES if w != wh]
            desc = tmpl.format(random.choice(others)) if '{}' in tmpl else tmpl

            cur.execute(
                'INSERT INTO transactions '
                '(warehouse_id, tx_date, tx_type, quantity, description) '
                'VALUES (?, ?, ?, ?, ?)',
                (wh, tx_date, tx_type, quantity, desc),
            )
            total += 1

    conn.commit()

    # Quick sanity check
    count = cur.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
    wh_count = cur.execute(
        'SELECT COUNT(DISTINCT warehouse_id) FROM transactions'
    ).fetchone()[0]
    conn.close()

    print(f'Created {DB_PATH} with {count} transactions across {wh_count} warehouses')
    assert count == total, f'Expected {total} rows, got {count}'
    assert wh_count == 5, f'Expected 5 warehouses, got {wh_count}'


if __name__ == '__main__':
    create_database()
