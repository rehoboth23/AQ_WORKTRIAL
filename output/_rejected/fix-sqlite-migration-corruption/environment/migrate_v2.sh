#!/bin/bash
set -euo pipefail

sqlite3 /app/store.db <<'EOSQL'
BEGIN TRANSACTION;

-- Add cost_price column to products table by recreating it
CREATE TABLE products_new (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    cost_price REAL NOT NULL DEFAULT 0.0,
    stock INTEGER NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id)
);

INSERT INTO products_new SELECT id, name, price, stock, category_id, 0.0 FROM products;

DROP TABLE products;
ALTER TABLE products_new RENAME TO products;

UPDATE metadata SET value = '2' WHERE key = 'schema_version';

COMMIT;
EOSQL
