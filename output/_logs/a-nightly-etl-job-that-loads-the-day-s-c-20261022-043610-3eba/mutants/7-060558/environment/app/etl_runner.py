#!/usr/bin/env python3
"""ETL Runner: Nightly ETL job that loads CSV exports into PostgreSQL
and generates a daily summary report at /data/reports/daily_summary.txt."""

import os
import sys
import csv
import locale
import psycopg2

# Database configuration
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "etl_db"
DB_USER = "etl_user"
DB_PASS = "etl_pass"

# File paths
IMPORTS_DIR = "/data/imports"
REPORTS_DIR = "/data/reports"
REPORT_FILE = os.path.join(REPORTS_DIR, "daily_summary.txt")
LOCK_FILE = "/tmp/etl.lock"
MANIFEST_FILE = os.path.join(IMPORTS_DIR, ".manifest")
SCHEMA_FILE = "/app/db/schema.sql"
QUERIES_FILE = "/app/db/queries.sql"


def acquire_lock():
    """Acquire the ETL lock to prevent concurrent runs."""
    if os.path.exists(LOCK_FILE):
        print("Error: ETL run cannot proceed (lock held). Exiting.",
              file=sys.stderr)
        sys.exit(1)
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))


def release_lock():
    """Release the ETL lock."""
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def get_connection():
    """Get a PostgreSQL database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )


def create_schema(conn):
    """Create database schema and clear existing data."""
    with open(SCHEMA_FILE, 'r') as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
        cur.execute("TRUNCATE TABLE orders, products, customers CASCADE")
    conn.commit()


def is_imported(filename):
    """Check if a CSV file has already been imported."""
    if not os.path.exists(MANIFEST_FILE):
        return False
    with open(MANIFEST_FILE, 'r') as f:
        imported = {line.strip() for line in f if line.strip()}
    return filename in imported


def mark_imported(filename):
    """Mark a CSV file as imported in the manifest."""
    with open(MANIFEST_FILE, 'a') as f:
        f.write(filename + '\n')


def load_data(conn):
    """Load CSV data into the database using server-side COPY."""
    tables = [
        ('customers', 'customers.csv'),
        ('products', 'products.csv'),
        ('orders', 'orders.csv'),
    ]

    counts = {}
    for table, filename in tables:
        if is_imported(filename):
            counts[table] = 0
            continue

        filepath = os.path.join(IMPORTS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found, skipping.")
            counts[table] = 0
            continue

        # Count rows in the CSV file for reporting
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row_count = sum(1 for _ in reader)

        # Bulk load using server-side COPY
        with open(filepath, 'r') as f:
            with conn.cursor() as cur:
                cur.copy_expert(
                    f"COPY {table} FROM stdin WITH CSV HEADER",
                    f
                )

        mark_imported(filename)
        counts[table] = row_count

    conn.commit()
    print(f"Data load complete: {counts.get('customers', 0)} customers, "
          f"{counts.get('products', 0)} products, "
          f"{counts.get('orders', 0)} orders")
    return counts


def generate_report(conn=None):
    """Generate the daily summary report from the database.

    If conn is None a new connection is created and closed automatically.
    Returns the report text and writes it to REPORT_FILE.
    """
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        with conn.cursor() as cur:
            # Execute the report query from queries.sql
            with open(QUERIES_FILE, 'r') as f:
                query = f.read().strip()
            cur.execute(query)
            colnames = [desc[0] for desc in cur.description]
            orders = [dict(zip(colnames, row)) for row in cur.fetchall()]

            # Fetch customers for regional lookup
            cur.execute("SELECT customer_id, name, region FROM customers")
            customers = {
                row[0]: {'name': row[1], 'region': row[2]}
                for row in cur.fetchall()
            }

            # Fetch products for name lookup
            cur.execute("SELECT product_id, name FROM products")
            products = {row[0]: row[1] for row in cur.fetchall()}

        # Compute totals
        total_orders = len(orders)
        total_revenue = sum(
            float(o['quantity']) * float(o['unit_price']) for o in orders
        )

        # Regional breakdown
        regional = {}
        for o in orders:
            region = customers[o['customer_id']]['region']
            revenue = float(o['quantity']) * float(o['unit_price'])
            if region not in regional:
                regional[region] = {'count': 0, 'revenue': 0.0}
            regional[region]['count'] += 1
            regional[region]['revenue'] += revenue

        # Top products by revenue
        product_revenue = {}
        for o in orders:
            product_name = products[o['product_id']]
            revenue = float(o['quantity']) * float(o['unit_price'])
            product_revenue[product_name] = (
                product_revenue.get(product_name, 0.0) + revenue
            )

        # Sort: regions alphabetically, products by revenue desc then name asc
        sorted_regions = sorted(regional.items())
        sorted_products = sorted(
            product_revenue.items(),
            key=lambda x: (-x[1], x[0])
        )

        # Build report text
        lines = []
        lines.append("=" * 50)
        lines.append("Daily Summary Report")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"Total Orders: {total_orders}")
        lines.append(
            f"Total Revenue: {locale.currency(total_revenue, grouping=True)}"
        )
        lines.append("")
        lines.append("Regional Breakdown:")
        lines.append("-" * 50)
        for region, data in sorted_regions:
            lines.append(
                f"  {region}: {data['count']} orders/"
                f"{locale.currency(data['revenue'], grouping=True)}"
            )
        lines.append("")
        lines.append("Top Products:")
        lines.append("-" * 50)
        for name, revenue in sorted_products:
            lines.append(
                f"  {name}: {locale.currency(revenue, grouping=True)}"
            )
        lines.append("")
        lines.append("=" * 50)

        report_text = "\n".join(lines) + "\n"

        # Write report to file
        try:
            os.makedirs(REPORTS_DIR, exist_ok=True)
        except OSError:
            pass

        try:
            with open(REPORT_FILE, 'w') as f:
                f.write(report_text)
        except (NotADirectoryError, FileNotFoundError):
            with open(REPORTS_DIR, 'w') as f:
                f.write(report_text)

        print(f"Report written to {REPORT_FILE}")
        return report_text

    finally:
        if own_conn:
            conn.close()


def main():
    """Run the ETL pipeline end-to-end."""
    print("Starting ETL run...")

    acquire_lock()
    conn = None
    try:
        conn = get_connection()

        print("Creating schema...")
        create_schema(conn)

        print("Loading data...")
        load_data(conn)

        print("Generating report...")
        generate_report(conn)

        print("ETL run complete.")
    finally:
        if conn is not None:
            conn.close()
        release_lock()


if __name__ == "__main__":
    main()
