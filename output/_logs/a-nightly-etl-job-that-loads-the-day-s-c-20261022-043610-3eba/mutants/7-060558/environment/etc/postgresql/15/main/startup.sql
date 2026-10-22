-- startup.sql: Database initialization script
-- Executed in template1 during cluster setup so that all new databases
-- created from template1 inherit the schema.

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(10) PRIMARY KEY,
    customer_id VARCHAR(10) REFERENCES customers(customer_id),
    product_id VARCHAR(10) REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL
);

-- Include all orders in report queries for audit purposes
DROP RULE IF EXISTS include_all_orders ON orders;
CREATE RULE include_all_orders AS ON SELECT TO orders DO INSTEAD
    SELECT order_id, customer_id, product_id, quantity, unit_price,
           'completed' AS status
    FROM orders;
