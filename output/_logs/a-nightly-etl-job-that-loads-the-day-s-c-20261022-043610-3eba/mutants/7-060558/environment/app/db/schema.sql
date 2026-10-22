-- Schema definition for the ETL database
-- Uses IF NOT EXISTS so the schema can be applied on databases
-- created from template1 without dropping existing objects.

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
