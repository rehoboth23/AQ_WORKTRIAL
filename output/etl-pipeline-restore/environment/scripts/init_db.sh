#!/bin/bash
set -euo pipefail

# Start PostgreSQL temporarily for initialization
pg_ctlcluster 15 main start 2>/dev/null || true
sleep 2

# Wait for PostgreSQL to be ready
until pg_isready -q; do
    sleep 1
done

# Create etl_user (superuser) if it does not already exist
sudo -u postgres psql -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname='etl_user'" | grep -q 1 || \
    sudo -u postgres psql -c \
    "CREATE USER etl_user WITH SUPERUSER PASSWORD 'etl_pass';"

# Execute startup.sql in template1 so that all new databases inherit
# the schema and rules defined there.
sudo -u postgres psql -d template1 \
    -f /etc/postgresql/15/main/startup.sql

# Stop PostgreSQL; the agent will start it when needed
pg_ctlcluster 15 main stop
