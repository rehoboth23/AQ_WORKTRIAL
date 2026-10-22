#!/usr/bin/env bash
# Run the Part 2 pipeline: generate -> band eval -> triage -> keep learnable, fair tasks.
# Usage:
#   bash scripts/pipeline.sh --topics scripts/topics.txt [--limit N]
#   bash scripts/pipeline.sh --eval-only output/<task> [output/<task> ...]
#   bash scripts/pipeline.sh --smoke output/<task>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 1 ]; then
    sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

# Make path arguments absolute before we cd into generator/ below.
ARGS=()
for a in "$@"; do
    if [ -e "$a" ]; then ARGS+=("$(cd "$(dirname "$a")" && pwd)/$(basename "$a")"); else ARGS+=("$a"); fi
done

# Prefer the repo's uv venv (Python 3.12); fall back to whatever `python` is on PATH.
PYTHON="$ROOT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python

cd "$ROOT_DIR/generator"
"$PYTHON" pipeline.py "${ARGS[@]}"
