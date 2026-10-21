#!/bin/bash
set -euo pipefail

sqlite3 /app/store.db <<'EOSQL'
CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO categories VALUES (1, 'Electronics');
INSERT INTO categories VALUES (2, 'Clothing');
INSERT INTO categories VALUES (3, 'Home');
INSERT INTO categories VALUES (4, 'Sports');
INSERT INTO categories VALUES (5, 'Books');

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id)
);

INSERT INTO products VALUES (1, 'Widget A', 9.99, 150, 1);
INSERT INTO products VALUES (2, 'Gadget B', 24.99, 300, 2);
INSERT INTO products VALUES (3, 'Doohickey C', 5.49, 75, 3);
INSERT INTO products VALUES (4, 'Thingamajig D', 49.99, 200, 4);
INSERT INTO products VALUES (5, 'Whatchamacallit E', 12.99, 50, 5);
INSERT INTO products VALUES (6, 'Gizmo F', 7.99, 120, 1);
INSERT INTO products VALUES (7, 'Contraption G', 34.99, 80, 2);
INSERT INTO products VALUES (8, 'Apparatus H', 19.99, 500, 3);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    total_price REAL NOT NULL,
    order_date TEXT NOT NULL
);

INSERT INTO orders VALUES (1, 1, 10, 99.90, '2024-01-15');
INSERT INTO orders VALUES (2, 3, 5, 27.45, '2024-01-16');
INSERT INTO orders VALUES (3, 5, 2, 25.98, '2024-01-17');
INSERT INTO orders VALUES (4, 7, 3, 104.97, '2024-01-18');
INSERT INTO orders VALUES (5, 8, 1, 19.99, '2024-01-19');

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO metadata VALUES ('schema_version', '1');
EOSQL
