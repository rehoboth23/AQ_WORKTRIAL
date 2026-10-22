#!/usr/bin/env python3
"""Build-time setup: creates all project files, system configs, and data."""
import os
import stat
import random
import json
from datetime import datetime, timedelta

def write_file(path, content, executable=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    if executable:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

# ============================================================
# System configuration
# Note: /etc/hosts and /etc/resolv.conf are read-only during
# Docker build, so we write them to .stage files and copy them
# at container startup via entrypoint.sh.
# ============================================================

write_file("/etc/hosts.stage", """\
127.0.0.1\tlocalhost
127.0.0.2\tapi.internal.local
127.0.0.1\tweb.internal.local
127.0.0.1\tdb.internal.local
127.0.0.1\tcache.internal.local
127.0.0.1\tauth.internal.local
127.0.0.1\tmail.internal.local
127.0.0.1\tntp.internal.local
127.0.0.1\tproxy.internal.local
127.0.0.1\tvpn.internal.local
127.0.0.1\tcdn.internal.local
127.0.0.1\tci.internal.local
127.0.0.1\tstaging.internal.local
127.0.0.1\tdev.internal.local
127.0.0.1\tqa.internal.local
127.0.0.1\tuat.internal.local
127.0.0.1\tdemo.internal.local
127.0.0.1\tdocs.internal.local
127.0.0.1\twiki.internal.local
127.0.0.1\tgit.internal.local
127.0.0.1\tregistry.internal.local
127.0.0.1\tmonitoring.internal.local
127.0.0.1\talerting.internal.local
127.0.0.1\tlogging.internal.local
127.0.0.1\tbackup.internal.local
::1\t\tlocalhost ip6-localhost ip6-loopback
ff02::1\t\tip6-allnodes
ff02::2\t\tip6-allrouters
""")

write_file("/etc/nsswitch.conf", """\
passwd:         files
group:          files
shadow:         files
gshadow:        files

hosts:          dns files
networks:       files

protocols:      db files
services:       db files
ethers:         db files
rpc:            db files

netgroup:       nis
""")

write_file("/etc/resolv.conf.stage", """\
nameserver 127.0.0.1
""")

write_file("/etc/dnsmasq.conf", """\
# Main dnsmasq configuration
conf-dir=/etc/dnsmasq.d/*.conf
addn-hosts=/etc/dnsmasq.hosts
user=root
""")

write_file("/etc/dnsmasq.hosts", """\
127.0.0.1 web.internal.local
127.0.0.1 db.internal.local
""")

# Clean any default files from the dnsmasq package
for f in os.listdir("/etc/dnsmasq.d/"):
    os.remove(os.path.join("/etc/dnsmasq.d/", f))

# dnsmasq.d configs
write_file("/etc/dnsmasq.d/00-network-base.conf", """\
# Network base address configuration
# Core infrastructure service addresses
# Last updated: 2024-01-15

# API services
address=/api.internal.local/127.0.0.2
address=/api-v2.internal.local/127.0.0.1
address=/api-gateway.internal.local/127.0.0.1

# Authentication and authorization
address=/auth.internal.local/127.0.0.1
address=/oauth.internal.local/127.0.0.1
address=/saml.internal.local/127.0.0.1

# Caching layer
address=/cache.internal.local/127.0.0.1
address=/redis.internal.local/127.0.0.1
address=/memcached.internal.local/127.0.0.1

# Database services
address=/db-replica.internal.local/127.0.0.1
address=/db-admin.internal.local/127.0.0.1

# Monitoring and observability
address=/monitoring.internal.local/127.0.0.1
address=/prometheus.internal.local/127.0.0.1
address=/grafana.internal.local/127.0.0.1

# Messaging and queues
address=/mq.internal.local/127.0.0.1
address=/rabbitmq.internal.local/127.0.0.1

# Network utilities
address=/ntp.internal.local/127.0.0.1
address=/proxy.internal.local/127.0.0.1
address=/vpn.internal.local/127.0.0.1
""")

write_file("/etc/dnsmasq.d/05-listen.conf", """\
listen-address=127.0.0.1
""")

write_file("/etc/dnsmasq.d/10-logging.conf", """\
# Debug logging enabled for DNS investigation
log-queries
log-facility=/var/log/dnsmasq-queries.log
""")

write_file("/etc/dnsmasq.d/15-caching.conf", """\
# Short TTL for testing - may need adjustment
local-ttl=5
cache-size=150
""")

write_file("/etc/dnsmasq.d/20-api-active.conf", """\
# Active API backend (v2)
address=/api.internal.local/127.0.0.1
""")

write_file("/etc/dnsmasq.d/25-database.conf", """\
# Database services
address=/db.internal.local/127.0.0.1
""")

write_file("/etc/dnsmasq.d/30-web.conf", """\
# Web frontend
address=/web.internal.local/127.0.0.1
""")

write_file("/etc/dnsmasq.d/35-legacy-rollback.conf", """\
# Legacy API backend - keep for rollback per migration plan
# DO NOT REMOVE until v2 is confirmed stable (30 days post-migration)
address=/api.internal.local/127.0.0.2
""")

write_file("/etc/dnsmasq.d/40-monitoring.conf", """\
server=8.8.8.8
edns-packet-max=4096
""")

# ============================================================
# Project tree
# ============================================================

# --- Backends ---

write_file("/app/backends/active_backend.py", """\
#!/usr/bin/env python3
\"\"\"Active backend (v2.0) for api.internal.local.

Binds to 127.0.0.1:8080 and serves JSON responses.
Supports health checks, metrics, and API endpoints.
\"\"\"

import json
import os
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Graceful shutdown flag
running = True

def signal_handler(signum, frame):
    global running
    running = False
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

START_TIME = datetime.now()

class ActiveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            uptime = (datetime.now() - START_TIME).total_seconds()
            body = json.dumps({
                "status": "healthy",
                "version": "2.0",
                "uptime_seconds": int(uptime),
            })
        elif self.path == "/metrics":
            body = json.dumps({
                "requests_total": 42857,
                "latency_p50_ms": 12,
                "latency_p99_ms": 45,
                "uptime_seconds": int((datetime.now() - START_TIME).total_seconds()),
                "backend": "active",
                "version": "2.0",
            })
        elif self.path == "/api/v2/status":
            body = json.dumps({
                "version": "2.0",
                "name": "active",
                "status": "healthy",
                "endpoints": ["/", "/healthz", "/metrics", "/api/v2/status"],
                "migration_complete": True,
            })
        else:
            body = json.dumps({
                "version": "2.0",
                "name": "active",
                "status": "healthy",
                "endpoints": ["/", "/healthz", "/metrics", "/api/v2/status"],
            })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend-Version", "2.0")
        self.send_header("X-Backend-Name", "active")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("ACTIVE_PORT", "8080"))
    host = os.environ.get("ACTIVE_IP", "127.0.0.1")
    server = HTTPServer((host, port), ActiveHandler)
    server.serve_forever()
""", executable=True)

write_file("/app/backends/legacy_backend.py", """\
#!/usr/bin/env python3
\"\"\"Legacy backend (v1.0) for api.internal.local.

Binds to 127.0.0.2:8080 and serves JSON responses.
This backend is DECOMMISSIONED but may still be running during transition.
\"\"\"

import json
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Graceful shutdown flag
running = True

def signal_handler(signum, frame):
    global running
    running = False
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

START_TIME = datetime.now()

class LegacyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            uptime = (datetime.now() - START_TIME).total_seconds()
            body = json.dumps({
                "status": "healthy",
                "version": "1.0",
                "uptime_seconds": int(uptime),
            })
        elif self.path == "/api/v1/status":
            body = json.dumps({
                "version": "1.0",
                "name": "legacy",
                "status": "healthy",
                "endpoints": ["/", "/healthz", "/api/v1/status"],
                "decommissioned": True,
            })
        else:
            body = json.dumps({
                "version": "1.0",
                "name": "legacy",
                "status": "healthy",
                "endpoints": ["/", "/healthz"],
            })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend-Version", "1.0")
        self.send_header("X-Backend-Name", "legacy")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.2", 8080), LegacyHandler)
    server.serve_forever()
""", executable=True)

write_file("/app/backends/backend_common.py", """\
#!/usr/bin/env python3
\"\"\"Common utilities shared by active and legacy backends.

Provides logging setup, configuration loading, and health check helpers.
\"\"\"

import json
import os
import logging
import sys
from datetime import datetime

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def setup_logging(name, level="INFO"):
    \"\"\"Configure logging for a backend service.\"\"\"
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    return logger

def load_config(path):
    \"\"\"Load a JSON configuration file.\"\"\"
    with open(path, "r") as f:
        return json.load(f)

def health_response(version, name, extra=None):
    \"\"\"Build a standard health response dict.\"\"\"
    resp = {
        "version": version,
        "name": name,
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }
    if extra:
        resp.update(extra)
    return resp

def read_env_config(prefix):
    \"\"\"Read environment variables with a given prefix.\"\"\"
    config = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            config[key[len(prefix):].lower()] = value
    return config

class BackendConfig:
    \"\"\"Configuration container for backend services.\"\"\"
    def __init__(self, host="127.0.0.1", port=8080, log_level="info",
                 workers=1, version="unknown", name="unknown"):
        self.host = host
        self.port = int(port)
        self.log_level = log_level
        self.workers = int(workers)
        self.version = version
        self.name = name

    @classmethod
    def from_env(cls, prefix="BACKEND_"):
        env = read_env_config(prefix)
        return cls(
            host=env.get("host", "127.0.0.1"),
            port=env.get("port", "8080"),
            log_level=env.get("log_level", "info"),
            workers=env.get("workers", "1"),
        )

    def to_dict(self):
        return {
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
            "workers": self.workers,
            "version": self.version,
            "name": self.name,
        }
""", executable=True)

# --- Bin scripts ---

write_file("/app/bin/healthcheck.py", """\
#!/usr/bin/env python3
\"\"\"Health check for internal API services.

Performs connectivity, version, and latency checks against configured backends.
Supports retry logic with exponential backoff and fallback IPs when DNS
resolution is unavailable.

Usage:
    python3 healthcheck.py [--verbose] [--service SVC] [--timeout SECS] [--retries N]
\"\"\"

import socket
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
import os
from datetime import datetime

# --- Configuration ---
MAX_RETRIES = 3
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10
BASE_RETRY_DELAY = 1
MAX_RETRY_DELAY = 30
LATENCY_WARN_MS = 500
LATENCY_CRIT_MS = 2000

# Services to monitor
SERVICES = {
    "api": {
        "domain": "api.internal.local",
        "port": 8080,
        "path": "/",
        "expected_version": "2.0",
        "critical": True,
        "description": "Core API service (v2 active)",
    },
}

# Fallback IPs used when DNS resolution fails entirely (dnsmasq down)
# These should match the current active backend IP for each service.
FALLBACK_IPS = {
    "api.internal.local": "127.0.0.2",
    "web.internal.local": "127.0.0.1",
    "db.internal.local": "127.0.0.1",
    "cache.internal.local": "127.0.0.1",
    "auth.internal.local": "127.0.0.1",
}

# --- State ---
verbose = False
check_start_time = None

# --- Logging ---
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{ts}] [{level}]"
    if level == "DEBUG" and not verbose:
        return
    print(f"{prefix} {msg}", flush=True)

def log_debug(msg):
    log(msg, "DEBUG")

def log_info(msg):
    log(msg, "INFO")

def log_warn(msg):
    log(msg, "WARN")

def log_error(msg):
    log(msg, "ERROR")

# --- DNS Resolution ---
def resolve_hostname(hostname):
    \"\"\"Resolve hostname via system resolver, falling back to hardcoded IPs.\"\"\"
    log_debug(f"Resolving hostname: {hostname}")
    try:
        ip = socket.gethostbyname(hostname)
        log_debug(f"Resolved {hostname} -> {ip} via system resolver")
        return ip
    except socket.gaierror as e:
        log_warn(f"DNS resolution failed for {hostname}: {e}")
        fallback = FALLBACK_IPS.get(hostname)
        if fallback:
            log_warn(f"Using fallback IP for {hostname}: {fallback}")
            return fallback
        log_error(f"No fallback IP configured for {hostname}")
        raise

# --- HTTP Client ---
def fetch_service_data(ip, port, domain, path="/", timeout=None):
    \"\"\"Fetch and parse JSON from a service endpoint.\"\"\"
    if timeout is None:
        timeout = CONNECT_TIMEOUT + READ_TIMEOUT
    url = f"http://{ip}:{port}{path}"
    headers = {
        "Host": domain,
        "User-Agent": "healthcheck/1.0",
        "Accept": "application/json",
    }
    log_debug(f"HTTP GET {url}")
    start = time.time()
    req = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
        body = response.read().decode("utf-8")
        elapsed_ms = (time.time() - start) * 1000
        log_debug(f"HTTP {response.status} in {elapsed_ms:.0f}ms ({len(body)} bytes)")
        data = json.loads(body)
        data["_latency_ms"] = round(elapsed_ms, 1)
        return data
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.time() - start) * 1000
        log_warn(f"HTTP {e.code} from {url} in {elapsed_ms:.0f}ms")
        raise
    except urllib.error.URLError as e:
        elapsed_ms = (time.time() - start) * 1000
        log_warn(f"Connection error for {url} after {elapsed_ms:.0f}ms: {e.reason}")
        raise
    except socket.timeout:
        elapsed_ms = (time.time() - start) * 1000
        log_warn(f"Timeout after {elapsed_ms:.0f}ms connecting to {url}")
        raise

# --- Retry Logic ---
def calculate_backoff(attempt):
    \"\"\"Exponential backoff with jitter.\"\"\"
    delay = min(BASE_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
    jitter = (os.getpid() % 100) / 1000.0
    return delay + jitter

def check_service_with_retry(name, config, retry_count=0):
    \"\"\"Check a service with retry and exponential backoff.\"\"\"
    domain = config["domain"]
    port = config["port"]
    path = config.get("path", "/")
    expected_version = config.get("expected_version")
    critical = config.get("critical", False)
    description = config.get("description", domain)

    log_info(f"Checking service '{name}' ({description})")

    try:
        ip = resolve_hostname(domain)
        data = fetch_service_data(ip, port, domain, path)

        version = data.get("version", "unknown")
        svc_name = data.get("name", "unknown")
        status = data.get("status", "unknown")
        latency = data.get("_latency_ms", 0)

        log_info(f"  {domain} -> {ip}:{port} | version={version} "
                 f"name={svc_name} status={status} latency={latency:.0f}ms")

        if expected_version and version != expected_version:
            log_error(f"  VERSION MISMATCH: expected={expected_version}, got={version}")
            return False

        if status == "error":
            log_error(f"  Service reports error status")
            return False

        if latency > LATENCY_CRIT_MS:
            log_warn(f"  High latency: {latency:.0f}ms (threshold: {LATENCY_CRIT_MS}ms)")

        log_info(f"  Service '{name}' is HEALTHY")
        return True

    except Exception as e:
        if retry_count < MAX_RETRIES:
            delay = calculate_backoff(retry_count)
            log_warn(f"  Attempt {retry_count + 1}/{MAX_RETRIES} failed: {e}")
            log_info(f"  Retrying in {delay:.1f}s...")
            time.sleep(delay)
            return check_service_with_retry(name, config, retry_count + 1)

        log_error(f"  Service '{name}' ({domain}) UNREACHABLE after "
                  f"{MAX_RETRIES} retries: {e}")
        return False

# --- Argument Parsing ---
def parse_args():
    parser = argparse.ArgumentParser(
        description="Internal service health check",
        epilog="Exit 0 if all critical services are healthy, 1 otherwise."
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug output")
    parser.add_argument("--service", "-s", type=str, default=None,
                        help="Check only a specific service")
    parser.add_argument("--timeout", "-t", type=int, default=None,
                        help="Connection timeout in seconds")
    parser.add_argument("--retries", "-r", type=int, default=None,
                        help="Maximum retry count")
    parser.add_argument("--json-output", "-j", action="store_true",
                        help="Output results as JSON")
    return parser.parse_args()

# --- Main ---
def main():
    global verbose, MAX_RETRIES, CONNECT_TIMEOUT

    args = parse_args()
    verbose = args.verbose

    if args.retries is not None:
        MAX_RETRIES = args.retries
    if args.timeout is not None:
        CONNECT_TIMEOUT = args.timeout

    check_start_time = time.time()
    log_info("=== Health Check Started ===")

    # Select services
    if args.service:
        if args.service not in SERVICES:
            log_error(f"Unknown service: {args.service}")
            log_info(f"Available: {', '.join(SERVICES.keys())}")
            sys.exit(2)
        targets = {args.service: SERVICES[args.service]}
    else:
        targets = SERVICES

    # Run checks
    results = {}
    all_critical_ok = True

    for name, config in targets.items():
        ok = check_service_with_retry(name, config)
        results[name] = {
            "healthy": ok,
            "domain": config["domain"],
            "critical": config.get("critical", False),
        }
        if not ok and config.get("critical", False):
            all_critical_ok = False

    elapsed = time.time() - check_start_time

    # Output
    if args.json_output:
        output = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "results": results,
            "overall": "PASS" if all_critical_ok else "FAIL",
        }
        print(json.dumps(output, indent=2))
    else:
        for name, result in results.items():
            status_str = "OK" if result["healthy"] else "FAIL"
            crit = " (critical)" if result["critical"] else ""
            log_info(f"  {name}: {status_str}{crit}")

    healthy = sum(1 for r in results.values() if r["healthy"])
    total = len(results)

    if all_critical_ok:
        log_info(f"=== HEALTHCHECK PASSED ({healthy}/{total} healthy) "
                 f"in {elapsed:.1f}s ===")
        sys.exit(0)
    else:
        log_error(f"=== HEALTHCHECK FAILED ({healthy}/{total} healthy) "
                  f"in {elapsed:.1f}s ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
""", executable=True)

write_file("/app/bin/start_services.sh", """\
#!/usr/bin/env bash
# Start all internal platform services.
# Sources environment configuration from /app/config/service.env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

# Source environment configuration
source "${APP_DIR}/config/service.env"
source "${APP_DIR}/config/active.env"

echo "Starting platform services..."

# Ensure resolv.conf points to local dnsmasq
echo "nameserver 127.0.0.1" > /etc/resolv.conf

# Ensure loopback addresses are available
ip addr add 127.0.0.2/8 dev lo 2>/dev/null || true

# Stop any existing dnsmasq
if [ -f /tmp/dnsmasq.pid ]; then
    kill "$(cat /tmp/dnsmasq.pid)" 2>/dev/null || true
    rm -f /tmp/dnsmasq.pid
    sleep 1
fi
pkill dnsmasq 2>/dev/null || true
sleep 1

# Start dnsmasq with rollback address configuration
# The ROLLBACK_ADDR flag provides a fallback address per migration plan
echo "Starting dnsmasq..."
dnsmasq --pid-file=/tmp/dnsmasq.pid ${ROLLBACK_ADDR:-}
echo "dnsmasq started"

# Wait for dnsmasq to be ready
sleep 1

# Start active backend
echo "Starting active backend on ${ACTIVE_IP}:${ACTIVE_PORT}..."
python3 "${APP_DIR}/backends/active_backend.py" &
echo "$!" > /tmp/active_backend.pid

# Start legacy backend (kept running for rollback readiness)
echo "Starting legacy backend on ${LEGACY_IP}:8080..."
python3 "${APP_DIR}/backends/legacy_backend.py" &
echo "$!" > /tmp/legacy_backend.pid

# Wait for backends to be ready
echo "Waiting for backends to be ready..."
for i in $(seq 1 10); do
    if curl -sf -o /dev/null http://127.0.0.1:8080/ 2>/dev/null && \\
       curl -sf -o /dev/null http://127.0.0.2:8080/ 2>/dev/null; then
        echo "All backends ready after ${i}s"
        break
    fi
    sleep 1
done

echo "All services started successfully"
echo "  dnsmasq: PID $(cat /tmp/dnsmasq.pid 2>/dev/null || echo '?')"
echo "  active backend: PID $(cat /tmp/active_backend.pid 2>/dev/null || echo '?') (${ACTIVE_IP}:${ACTIVE_PORT})"
echo "  legacy backend: PID $(cat /tmp/legacy_backend.pid 2>/dev/null || echo '?') (${LEGACY_IP}:8080)"
""", executable=True)

write_file("/app/bin/stop_services.sh", """\
#!/usr/bin/env bash
# Stop all platform services gracefully.

set -euo pipefail

echo "Stopping platform services..."

for pidfile in /tmp/active_backend.pid /tmp/legacy_backend.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        kill "$pid" 2>/dev/null || true
        rm -f "$pidfile"
        echo "Stopped PID $pid"
    fi
done

if [ -f /tmp/dnsmasq.pid ]; then
    pid=$(cat /tmp/dnsmasq.pid)
    kill "$pid" 2>/dev/null || true
    rm -f /tmp/dnsmasq.pid
    echo "Stopped dnsmasq PID $pid"
fi

pkill -f "active_backend.py" 2>/dev/null || true
pkill -f "legacy_backend.py" 2>/dev/null || true
pkill dnsmasq 2>/dev/null || true

echo "All services stopped"
""", executable=True)

write_file("/app/bin/reload_dns.sh", """\
#!/usr/bin/env bash
# Reload dnsmasq configuration by sending SIGHUP.

set -euo pipefail

if [ -f /tmp/dnsmasq.pid ]; then
    pid=$(cat /tmp/dnsmasq.pid)
    kill -HUP "$pid" 2>/dev/null
    echo "Sent SIGHUP to dnsmasq (PID $pid)"
else
    echo "ERROR: dnsmasq PID file not found at /tmp/dnsmasq.pid"
    exit 1
fi
""", executable=True)

write_file("/app/bin/deploy.sh", """\
#!/usr/bin/env bash
# Deployment script for internal platform services.
# Reads version info and applies configuration changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_ENV="${DEPLOY_ENV:-production}"

echo "=== Platform Deployment ==="
echo "Environment: ${DEPLOY_ENV}"
echo "Timestamp: $(date -Iseconds)"

# Load service configuration
source "${APP_DIR}/config/service.env"
source "${APP_DIR}/config/active.env"

# Verify backend configuration
if [ -z "${ACTIVE_IP:-}" ] || [ -z "${ACTIVE_PORT:-}" ]; then
    echo "ERROR: Active backend not configured"
    exit 1
fi

echo "Active backend: ${ACTIVE_IP}:${ACTIVE_PORT}"
echo "Legacy backend: ${LEGACY_IP:-unknown}:${LEGACY_PORT:-unknown}"

# Check backend health before deployment
echo "Checking backend availability..."
if curl -sf -o /dev/null "http://${ACTIVE_IP}:${ACTIVE_PORT}/healthz" 2>/dev/null; then
    echo "Active backend is healthy"
else
    echo "WARNING: Active backend not responding"
fi

# Verify DNS configuration
echo "Checking DNS configuration..."
if command -v dig &>/dev/null; then
    dns_result=$(dig +short "api.internal.local" @127.0.0.1 2>/dev/null || echo "failed")
    echo "DNS resolves api.internal.local to: ${dns_result}"
fi

echo "Deployment pre-check complete"
echo "Run start_services.sh to apply changes"
""", executable=True)

write_file("/app/bin/verify_config.sh", """\
#!/usr/bin/env bash
# Verify platform configuration consistency.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Configuration Verification ==="

# Check nsswitch order
echo "Checking nsswitch.conf..."
nsswitch_hosts=$(grep '^hosts:' /etc/nsswitch.conf 2>/dev/null || echo "NOT FOUND")
echo "  hosts line: ${nsswitch_hosts}"

# Check /etc/hosts for api entry
echo "Checking /etc/hosts..."
hosts_api=$(grep 'api.internal.local' /etc/hosts 2>/dev/null || echo "NOT FOUND")
echo "  api.internal.local entry: ${hosts_api}"

# Check dnsmasq address directives
echo "Checking dnsmasq configuration..."
for conf in /etc/dnsmasq.d/*.conf; do
    matches=$(grep 'api.internal.local' "$conf" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        echo "  ${conf}:"
        echo "$matches" | while IFS= read -r line; do
            echo "    $line"
        done
    fi
done

# Check service.env
echo "Checking service.env..."
if [ -f "${APP_DIR}/config/service.env" ]; then
    grep -E '^(ACTIVE_IP|LEGACY_IP|ROLLBACK_ADDR|API_SERVICE_DOMAIN)=' \\
        "${APP_DIR}/config/service.env" 2>/dev/null || echo "  (no matches)"
fi

echo "Verification complete"
""", executable=True)

# --- Config ---

write_file("/app/config/service.env", """\
# Service environment configuration
# Updated during v1 -> v2 migration

API_SERVICE_DOMAIN=api.internal.local
ACTIVE_IP=127.0.0.1
LEGACY_IP=127.0.0.2
LEGACY_PORT=8080

# Rollback address directive for dnsmasq
# Per migration plan, keep rollback capability until v2 is stable
ROLLBACK_ADDR="--address=/${API_SERVICE_DOMAIN}/${LEGACY_IP}"
""")

write_file("/app/config/active.env", """\
# Active backend configuration
ACTIVE_PORT=8080
ACTIVE_LOG_LEVEL=info
ACTIVE_WORKERS=1
""")

write_file("/app/config/backends.json", """\
{
  "backends": [
    {
      "name": "active",
      "version": "2.0",
      "host": "127.0.0.1",
      "port": 8080,
      "status": "active"
    },
    {
      "name": "legacy",
      "version": "1.0",
      "host": "127.0.0.2",
      "port": 8080,
      "status": "standby"
    }
  ]
}
""")

write_file("/app/config/resolver.json", """\
{
  "resolver": {
    "type": "dnsmasq",
    "address": "127.0.0.1",
    "port": 53,
    "protocol": "udp",
    "cache": {
      "enabled": true,
      "ttl": 300,
      "max_entries": 150
    },
    "upstream": {
      "servers": ["8.8.8.8"],
      "timeout": 5
    }
  }
}
""")

write_file("/app/config/dnsmasq_template.conf", """\
# Template for dnsmasq configuration generation
# This file is NOT used by dnsmasq directly - it is a reference only

# Listen address
listen-address=127.0.0.1

# Upstream DNS
server=8.8.8.8
server=8.8.4.4

# Cache settings
cache-size=1000
local-ttl=300

# Logging
log-queries
log-facility=/var/log/dnsmasq.log

# Hosts file
addn-hosts=/etc/dnsmasq.hosts

# Config directory
conf-dir=/etc/dnsmasq.d/*.conf
""")

# --- Docs ---

write_file("/app/docs/MIGRATION.md", """\
# API Service Migration: v1 to v2

## Overview
The API service (`api.internal.local`) has been migrated from the legacy
backend (v1.0 at 127.0.0.2:8080) to the active backend (v2.0 at 127.0.0.1:8080).

## Completed Steps
- [x] Deploy active backend v2.0
- [x] Update dnsmasq configuration to point api.internal.local to 127.0.0.1
- [x] **Update /etc/hosts to point api.internal.local to 127.0.0.1**
- [x] Update healthcheck expected version to 2.0
- [x] Update service.env with new IPs

## Rollback Plan
If v2 has issues, revert by:
1. Stop active backend
2. Set `address=/api.internal.local/127.0.0.2` in dnsmasq
3. Restart dnsmasq

## Post-Migration
- Legacy backend kept running for 30-day rollback window
- 35-legacy-rollback.conf will be removed after stability period
""")

write_file("/app/docs/ARCHITECTURE.md", """\
# System Architecture

## DNS Resolution Chain
1. Application calls system resolver (gethostbyname)
2. /etc/nsswitch.conf determines lookup order
3. Currently configured as: hosts: dns files
4. DNS queries go to 127.0.0.1 (local dnsmasq)
5. dnsmasq serves addresses from:
   - /etc/dnsmasq.d/*.conf files
   - /etc/dnsmasq.hosts file
   - Command-line address flags

## Backends
- **Active (v2.0)**: 127.0.0.1:8080
- **Legacy (v1.0)**: 127.0.0.2:8080 (decommissioned)

## Service Startup
Run `/app/bin/start_services.sh` to start all services.
Run `/app/bin/stop_services.sh` to stop all services.
Run `/app/bin/reload_dns.sh` to reload dnsmasq config.

## Configuration Files
| File | Purpose |
|------|---------|
| /etc/hosts | Static host mappings |
| /etc/nsswitch.conf | Name service switch order |
| /etc/resolv.conf | DNS resolver configuration |
| /etc/dnsmasq.conf | Main dnsmasq config |
| /etc/dnsmasq.d/ | dnsmasq config drop-in directory |
| /etc/dnsmasq.hosts | Additional host mappings for dnsmasq |
| /app/config/service.env | Service IP and port definitions |
| /app/config/active.env | Active backend environment vars |

## Network Layout
All services bind to loopback (127.0.0.0/8). The active backend uses
127.0.0.1:8080, the legacy backend uses 127.0.0.2:8080. Dnsmasq
listens on 127.0.0.1:53 for DNS queries.
""")

write_file("/app/docs/RUNBOOK.md", """\
# Operational Runbook

## Intermittent DNS Resolution Issues

### Symptoms
- Health check sometimes reports wrong backend version
- Connection to decommissioned backend intermittently

### Investigation Steps
1. Check dnsmasq cache TTL (currently set to 5s in 15-caching.conf)
2. Short TTL may cause frequent re-resolution with inconsistent results
3. Consider increasing local-ttl to 60 or 300 seconds
4. Check dnsmasq cache size (currently 150)
5. Monitor cache hit/miss ratio

### Resolution
- Increase local-ttl in /etc/dnsmasq.d/15-caching.conf
- Increase cache-size if needed
- Reload dnsmasq: `bash /app/bin/reload_dns.sh`

## Service Restart Procedure
1. Run `/app/bin/stop_services.sh`
2. Wait 5 seconds for graceful shutdown
3. Run `/app/bin/start_services.sh`
4. Verify with `python3 /app/bin/healthcheck.py`

## Emergency Rollback
If the active backend fails:
1. Edit /app/config/service.env to swap ACTIVE_IP and LEGACY_IP
2. Restart services via start_services.sh
3. The ROLLBACK_ADDR in service.env will reconfigure dnsmasq
""")

write_file("/app/docs/TROUBLESHOOTING.md", """\
# Troubleshooting Guide

## DNS Resolution Problems

### dnsmasq Not Responding
1. Check if dnsmasq is running: `ps aux | grep dnsmasq`
2. Check logs: `cat /var/log/dnsmasq-queries.log`
3. Verify /etc/resolv.conf points to 127.0.0.1

### Intermittent Failures
1. Check dnsmasq restart timing - brief outages during reload
2. Healthcheck uses fallback IPs during DNS outages
3. Verify fallback IPs match current backend configuration
4. Check for timing issues between service startup and first health check

### Common Issues
- dnsmasq conf files processed in alphabetical order
- CLI flags override conf file settings
- addn-hosts file entries are additive

## Backend Connectivity

### Cannot Reach Active Backend
1. Verify 127.0.0.1 is assigned: `ip addr show lo`
2. Check backend process: `ps aux | grep active_backend`
3. Test direct: `curl http://127.0.0.1:8080/`

### Cannot Reach Legacy Backend
1. Verify 127.0.0.2 is assigned: `ip addr show lo`
2. Check backend process: `ps aux | grep legacy_backend`
3. Test direct: `curl http://127.0.0.2:8080/`

## Configuration Verification
Run `/app/bin/verify_config.sh` for an automated check of key config files.
""")

write_file("/app/docs/CHANGELOG.md", """\
# Changelog

## [2.0.0] - 2024-01-20
### Added
- Active backend v2.0 deployed at 127.0.0.1:8080
- New /api/v2/status endpoint
- Health check updated to expect version 2.0
- 20-api-active.conf added to dnsmasq config

### Changed
- API_SERVICE_DOMAIN now points to active backend
- ACTIVE_IP changed from 127.0.0.2 to 127.0.0.1

### Deprecated
- Legacy backend v1.0 (30-day decommission window)
- 35-legacy-rollback.conf (remove after stability period)

## [1.0.0] - 2023-11-01
### Added
- Initial deployment of legacy backend at 127.0.0.2:8080
- dnsmasq configuration with 00-network-base.conf
- Health check with fallback IP logic
- /etc/hosts entries for all internal services
""")

# --- Monitoring (decoys) ---

write_file("/app/monitoring/collect_metrics.py", """\
#!/usr/bin/env python3
\"\"\"Collect DNS timing metrics for monitoring.\"\"\"

import subprocess
import time
import json
import statistics
from datetime import datetime

DOMAINS = [
    "api.internal.local",
    "web.internal.local",
    "db.internal.local",
    "cache.internal.local",
    "auth.internal.local",
]

SAMPLE_COUNT = 5
DIG_TIMEOUT = 2

def measure_dns_time(domain, server="127.0.0.1"):
    start = time.time()
    try:
        result = subprocess.run(
            ["dig", "+short", f"@{server}", domain],
            capture_output=True, text=True, timeout=DIG_TIMEOUT
        )
        elapsed = time.time() - start
        return {
            "domain": domain,
            "time_ms": round(elapsed * 1000, 2),
            "status": "ok" if result.returncode == 0 else "error",
            "result": result.stdout.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"domain": domain, "time_ms": None, "status": "timeout", "result": None}

def collect_metrics():
    metrics = {"timestamp": datetime.now().isoformat(), "measurements": {}}
    for domain in DOMAINS:
        times = []
        for _ in range(SAMPLE_COUNT):
            m = measure_dns_time(domain)
            if m["time_ms"] is not None:
                times.append(m["time_ms"])
            time.sleep(0.1)
        if times:
            metrics["measurements"][domain] = {
                "samples": len(times),
                "mean_ms": round(statistics.mean(times), 2),
                "min_ms": round(min(times), 2),
                "max_ms": round(max(times), 2),
                "stdev_ms": round(statistics.stdev(times), 2) if len(times) > 1 else 0,
            }
        else:
            metrics["measurements"][domain] = {"samples": 0, "error": "timeout"}
    return metrics

def main():
    print(json.dumps(collect_metrics(), indent=2))

if __name__ == "__main__":
    main()
""", executable=True)

write_file("/app/monitoring/check_dns_latency.py", """\
#!/usr/bin/env python3
\"\"\"Check DNS latency against thresholds.\"\"\"

import subprocess
import sys
import json
import time

THRESHOLD_MS = 50
DOMAINS = ["api.internal.local", "web.internal.local", "db.internal.local"]

def check_latency(domain, threshold_ms=THRESHOLD_MS):
    start = time.time()
    result = subprocess.run(
        ["dig", "+short", "@127.0.0.1", domain],
        capture_output=True, text=True, timeout=5
    )
    elapsed_ms = (time.time() - start) * 1000
    status = "OK" if elapsed_ms < threshold_ms else "SLOW"
    return {"domain": domain, "latency_ms": round(elapsed_ms, 2), "status": status}

def main():
    results = [check_latency(d) for d in DOMAINS]
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(r["status"] == "OK" for r in results) else 1)

if __name__ == "__main__":
    main()
""", executable=True)

write_file("/app/monitoring/alert_rules.json", """\
{
  "rules": [
    {
      "name": "dns_latency_high",
      "metric": "dns.latency_ms",
      "threshold": 50,
      "operator": ">",
      "severity": "warning"
    },
    {
      "name": "dns_timeout",
      "metric": "dns.timeout_count",
      "threshold": 3,
      "operator": ">",
      "severity": "critical"
    },
    {
      "name": "backend_version_mismatch",
      "metric": "healthcheck.version",
      "expected": "2.0",
      "severity": "critical"
    }
  ]
}
""")

write_file("/app/monitoring/dns_watchdog.py", """\
#!/usr/bin/env python3
\"\"\"DNS watchdog - continuously monitors DNS resolution consistency.

Runs periodic DNS queries and alerts on inconsistencies between
expected and actual results. This is a monitoring tool only and
does not modify any configuration.

Usage:
    python3 dns_watchdog.py [--interval SECONDS] [--count N]
\"\"\"

import subprocess
import time
import json
import sys
from datetime import datetime
from collections import defaultdict

EXPECTED_RESOLUTIONS = {
    "api.internal.local": ["127.0.0.1"],
    "web.internal.local": ["127.0.0.1"],
    "db.internal.local": ["127.0.0.1"],
    "cache.internal.local": ["127.0.0.1"],
    "auth.internal.local": ["127.0.0.1"],
}

def dig_domain(domain, server="127.0.0.1"):
    \"\"\"Resolve a domain via dig and return list of IPs.\"\"\"
    try:
        result = subprocess.run(
            ["dig", "+short", f"@{server}", domain],
            capture_output=True, text=True, timeout=5
        )
        ips = [line.strip() for line in result.stdout.strip().split("\\n") if line.strip()]
        return ips
    except Exception as e:
        return [f"ERROR: {e}"]

def check_consistency(domain, results_history):
    \"\"\"Check if resolution results have been inconsistent.\"\"\"
    if len(results_history) < 2:
        return "insufficient_data"
    unique_results = set(tuple(sorted(r)) for r in results_history[-10:])
    if len(unique_results) > 1:
        return "inconsistent"
    return "consistent"

def main():
    interval = 5
    count = 100
    for arg_idx in range(1, len(sys.argv)):
        if sys.argv[arg_idx] == "--interval" and arg_idx + 1 < len(sys.argv):
            interval = int(sys.argv[arg_idx + 1])
        elif sys.argv[arg_idx] == "--count" and arg_idx + 1 < len(sys.argv):
            count = int(sys.argv[arg_idx + 1])

    history = defaultdict(list)
    print(f"Starting DNS watchdog (interval={interval}s, count={count})")
    for i in range(count):
        timestamp = datetime.now().isoformat()
        for domain in EXPECTED_RESOLUTIONS:
            ips = dig_domain(domain)
            history[domain].append(ips)
            consistency = check_consistency(domain, history[domain])
            expected = EXPECTED_RESOLUTIONS[domain]
            match = ips == expected
            status = "OK" if match else "MISMATCH"
            if not match or consistency == "inconsistent":
                print(f"[{timestamp}] {domain}: {ips} (expected {expected}) "
                      f"consistency={consistency} status={status}")
        time.sleep(interval)

if __name__ == "__main__":
    main()
""", executable=True)

# --- Integration test (decoy) ---

write_file("/app/tests/integration_test.py", """\
#!/usr/bin/env python3
\"\"\"Integration tests for backend response format validation.\"\"\"

import json
import subprocess
import sys
import urllib.request

def test_active_backend_format():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:8080/", timeout=5)
        data = json.loads(response.read().decode())
        assert "version" in data
        assert "name" in data
        assert "status" in data
        assert isinstance(data.get("endpoints"), list)
        print("PASS: active backend format correct")
        return True
    except Exception as e:
        print(f"FAIL: active backend format: {e}")
        return False

def test_legacy_backend_format():
    try:
        response = urllib.request.urlopen("http://127.0.0.2:8080/", timeout=5)
        data = json.loads(response.read().decode())
        assert "version" in data
        assert "name" in data
        print("PASS: legacy backend format correct")
        return True
    except Exception as e:
        print(f"FAIL: legacy backend format: {e}")
        return False

def test_dns_resolution():
    try:
        result = subprocess.run(
            ["dig", "+short", "api.internal.local", "@127.0.0.1"],
            capture_output=True, text=True, timeout=5
        )
        ips = result.stdout.strip().split("\\n")
        assert len(ips) > 0
        print(f"PASS: DNS returns {len(ips)} result(s)")
        return True
    except Exception as e:
        print(f"FAIL: DNS resolution: {e}")
        return False

def test_backend_headers():
    \"\"\"Verify backend response headers contain version info.\"\"\"
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/")
        response = urllib.request.urlopen(req, timeout=5)
        version_header = response.headers.get("X-Backend-Version", "")
        name_header = response.headers.get("X-Backend-Name", "")
        if version_header and name_header:
            print(f"PASS: backend headers present (version={version_header}, name={name_header})")
            return True
        else:
            print(f"FAIL: missing backend headers")
            return False
    except Exception as e:
        print(f"FAIL: backend header check: {e}")
        return False

def main():
    results = [
        test_active_backend_format(),
        test_legacy_backend_format(),
        test_dns_resolution(),
        test_backend_headers(),
    ]
    print(f"{'All' if all(results) else sum(not r for r in results)} tests {'PASSED' if all(results) else 'FAILED'}")
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
""", executable=True)

write_file("/app/tests/unit/test_backend_common.py", """\
#!/usr/bin/env python3
\"\"\"Unit tests for backend_common module.\"\"\"

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backends'))

from backend_common import BackendConfig, health_response, setup_logging

def test_backend_config_defaults():
    config = BackendConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 8080
    assert config.log_level == "info"
    assert config.workers == 1
    print("PASS: BackendConfig defaults")

def test_backend_config_custom():
    config = BackendConfig(host="10.0.0.1", port=9090, log_level="debug", workers=4)
    assert config.host == "10.0.0.1"
    assert config.port == 9090
    assert config.log_level == "debug"
    assert config.workers == 4
    print("PASS: BackendConfig custom values")

def test_health_response():
    resp = health_response("2.0", "active")
    assert resp["version"] == "2.0"
    assert resp["name"] == "active"
    assert resp["status"] == "healthy"
    assert "timestamp" in resp
    print("PASS: health_response structure")

def test_health_response_with_extra():
    resp = health_response("1.0", "legacy", extra={"decommissioned": True})
    assert resp["decommissioned"] is True
    print("PASS: health_response with extra fields")

def test_backend_config_to_dict():
    config = BackendConfig(version="2.0", name="active")
    d = config.to_dict()
    assert d["version"] == "2.0"
    assert d["name"] == "active"
    assert d["host"] == "127.0.0.1"
    print("PASS: BackendConfig.to_dict()")

if __name__ == "__main__":
    test_backend_config_defaults()
    test_backend_config_custom()
    test_health_response()
    test_health_response_with_extra()
    test_backend_config_to_dict()
    print("All unit tests passed")
""", executable=True)

# ============================================================
# Bulky data generation
# ============================================================

random.seed(42)

# Access log
log_lines = []
base_time = datetime(2024, 1, 10, 0, 0, 0)
methods = ["GET", "POST", "PUT", "DELETE"]
paths = ["/api/v1/users", "/api/v1/orders", "/api/v1/products", "/api/v1/auth",
         "/api/v2/users", "/api/v2/orders", "/api/v2/health", "/healthz", "/metrics"]
statuses = [200, 200, 200, 200, 201, 204, 301, 400, 404, 500]
agents = ["curl/7.88", "healthcheck/1.0", "python-requests/2.28", "internal-client/3.1"]

for i in range(800):
    ts = base_time + timedelta(minutes=i * 3 + random.randint(0, 120))
    method = random.choice(methods)
    path = random.choice(paths)
    status = random.choice(statuses)
    size = random.randint(100, 50000)
    duration = random.randint(1, 500)
    ip = random.choice(["127.0.0.1", "127.0.0.2", "10.0.0.1", "10.0.0.2"])
    agent = random.choice(agents)
    log_lines.append(
        f'{ip} - - [{ts.strftime("%d/%b/%Y:%H:%M:%S")} +0000] '
        f'"{method} {path} HTTP/1.1" {status} {size} '
        f'"-" "{agent}" {duration}ms'
    )

write_file("/app/logs/access.log", "\n".join(log_lines) + "\n")

# dnsmasq query log
dns_log_lines = []
query_types = ["A", "AAAA", "SRV"]
domains = ["api.internal.local", "web.internal.local", "db.internal.local",
           "cache.internal.local", "auth.internal.local", "prometheus.internal.local",
           "grafana.internal.local", "mq.internal.local", "redis.internal.local"]

for i in range(300):
    ts = base_time + timedelta(minutes=i * 5 + random.randint(0, 200))
    domain = random.choice(domains)
    qtype = random.choice(query_types)
    result = random.choice(["127.0.0.1", "127.0.0.2", "NXDOMAIN"])
    dns_log_lines.append(
        f'{ts.strftime("%b %d %H:%M:%S")} dnsmasq[{1000 + i % 50}]: '
        f'query[{qtype}] {domain} from 127.0.0.1 -> {result}'
    )

write_file("/app/logs/dnsmasq-queries.log", "\n".join(dns_log_lines) + "\n")

# Error log (decoy - contains misleading errors about TTL and caching)
error_log_lines = []
for i in range(150):
    ts = base_time + timedelta(minutes=i * 8 + random.randint(0, 300))
    level = random.choice(["WARNING", "WARNING", "INFO", "ERROR"])
    if level == "WARNING":
        msg = random.choice([
            "DNS cache entry expired before reuse (TTL=5s too short?)",
            "High cache miss ratio detected - consider increasing cache-size",
            "Short TTL causing excessive re-resolution queries",
            "Cache pressure: 150 entries may be insufficient for current load",
        ])
    elif level == "ERROR":
        msg = random.choice([
            "Temporary DNS resolution failure - fallback IP used",
            "Connection timeout to api.internal.local - retrying",
            "DNS query returned unexpected result count",
        ])
    else:
        msg = random.choice([
            "Health check completed successfully",
            "DNS resolution within normal parameters",
            "Backend response time acceptable",
        ])
    error_log_lines.append(
        f'{ts.strftime("%Y-%m-%d %H:%M:%S")} [{level}] {msg}'
    )

write_file("/app/logs/error.log", "\n".join(error_log_lines) + "\n")

# Monitoring data files
for day_offset in range(5):
    day = datetime(2024, 1, 12) + timedelta(days=day_offset)
    metrics = []
    for hour in range(24):
        for minute in range(0, 60, 5):
            ts = day + timedelta(hours=hour, minutes=minute)
            metrics.append({
                "timestamp": ts.isoformat(),
                "dns_latency_ms": round(random.uniform(0.5, 15.0), 2),
                "api_response_ms": round(random.uniform(5, 120), 1),
                "cache_hit_ratio": round(random.uniform(0.7, 0.99), 3),
                "active_connections": random.randint(10, 200),
            })
    fname = day.strftime("/app/monitoring/data/metrics_%Y_%m_%d.json")
    write_file(fname, json.dumps(metrics, indent=1) + "\n")

# Health check history log (decoy showing intermittent results)
health_history = []
for i in range(200):
    ts = base_time + timedelta(minutes=i * 15)
    # Simulate intermittent results: ~50% v1, ~50% v2
    if random.random() < 0.5:
        version = "2.0"
        backend = "active"
        ip = "127.0.0.1"
    else:
        version = "1.0"
        backend = "legacy"
        ip = "127.0.0.2"
    health_history.append(
        f'{ts.strftime("%Y-%m-%d %H:%M:%S")} api.internal.local -> {ip}:8080 '
        f'version={version} name={backend} status=healthy latency={random.randint(1, 50)}ms'
    )

write_file("/app/logs/healthcheck_history.log", "\n".join(health_history) + "\n")

# Service registry (decoy - not used by any service)
service_registry = {
    "services": [
        {
            "name": "api",
            "domain": "api.internal.local",
            "backends": [
                {"version": "2.0", "host": "127.0.0.1", "port": 8080, "weight": 100, "active": True},
                {"version": "1.0", "host": "127.0.0.2", "port": 8080, "weight": 0, "active": False},
            ],
            "health_check": {"path": "/healthz", "interval_seconds": 30, "timeout_seconds": 5},
            "dns": {"resolver": "dnsmasq", "ttl": 5},
        },
        {
            "name": "web",
            "domain": "web.internal.local",
            "backends": [
                {"version": "1.5", "host": "127.0.0.1", "port": 8081, "weight": 100, "active": True},
            ],
            "health_check": {"path": "/healthz", "interval_seconds": 30, "timeout_seconds": 5},
        },
        {
            "name": "db",
            "domain": "db.internal.local",
            "backends": [
                {"version": "14.2", "host": "127.0.0.1", "port": 5432, "weight": 100, "active": True},
            ],
        },
    ],
    "metadata": {
        "last_updated": "2024-01-20T10:30:00Z",
        "format_version": "1.2",
        "generated_by": "service-registry-manager",
    }
}

write_file("/app/config/service_registry.json", json.dumps(service_registry, indent=2) + "\n")

print("Environment setup complete.")
