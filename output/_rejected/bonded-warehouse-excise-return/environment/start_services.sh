#!/usr/bin/env bash
set -e

# Kill any existing services on our ports
for port in 5001 5002 5003; do
    fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 1

# Start services in background
python3 /app/services/erp.py    > /tmp/erp.log    2>&1 &
python3 /app/services/ledger.py > /tmp/ledger.log 2>&1 &
python3 /app/services/portal.py > /tmp/portal.log 2>&1 &

# Wait for each service to accept connections
for port in 5001 5002 5003; do
    for i in $(seq 1 60); do
        if python3 -c "
import socket, sys
s = socket.socket()
s.settimeout(1)
try:
    s.connect(('localhost', $port))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            break
        fi
        sleep 0.5
    done
done

echo "All services started on ports 5001, 5002, 5003"
