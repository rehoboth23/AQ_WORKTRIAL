#!/bin/bash
set -e

cd /app/services

# Kill any existing instances of the services
pkill -f formulary_service.py 2>/dev/null || true
pkill -f prescriber_service.py 2>/dev/null || true
pkill -f payer_service.py 2>/dev/null || true
pkill -f portal.py 2>/dev/null || true

sleep 1

# Start all services in background
python3 formulary_service.py &
python3 prescriber_service.py &
python3 payer_service.py &
python3 portal.py &

# Wait for services to be ready
echo "Waiting for services to start..."
for i in $(seq 1 30); do
    if python3 -c "
import urllib.request
for port in [5001, 5002, 5003, 5004]:
    try:
        urllib.request.urlopen(f'http://localhost:{port}/', timeout=1)
    except Exception:
        exit(1)
" 2>/dev/null; then
        echo "All services started"
        exit 0
    fi
    sleep 0.5
done

echo "Warning: Some services may not have started within timeout"
