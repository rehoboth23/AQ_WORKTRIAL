#!/usr/bin/env bash
# Keep jobs/dashboard.html up to date (re-render every N seconds; default 15). Ctrl-C to stop.
# Open jobs/dashboard.html in a browser; the page reloads itself.
# Usage: bash scripts/dashboard.sh [seconds]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="$ROOT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python
INTERVAL="${1:-15}"

cd "$ROOT_DIR/generator"
echo "Dashboard: $ROOT_DIR/jobs/dashboard.html (every ${INTERVAL}s)"
while true; do
    "$PYTHON" status.py || echo "status.py failed; retrying" >&2
    sleep "$INTERVAL"
done
