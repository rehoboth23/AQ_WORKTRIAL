#!/usr/bin/env bash
# Run the structural validator on a generated task.
# Usage: bash scripts/validate.sh output/my-task

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 1 ]; then
    echo "Usage: bash scripts/validate.sh <task_dir>"
    echo "Example: bash scripts/validate.sh output/fix-a-memory-bug-in-a-c-ring-buffer"
    exit 1
fi

# Make the task dir absolute before we cd into validator/ below. Callers can pass
# an absolute path, one relative to their cwd, or one relative to the repo root
# (e.g. examples/csv-normalizer). If neither exists, pass it through unchanged so
# the validator reports the missing directory.
TASK_DIR="$1"
if [ -d "$TASK_DIR" ]; then
    TASK_DIR="$(cd "$TASK_DIR" && pwd)"
elif [ -d "$ROOT_DIR/$TASK_DIR" ]; then
    TASK_DIR="$(cd "$ROOT_DIR/$TASK_DIR" && pwd)"
fi

# Prefer the repo's uv venv (Python 3.12); fall back to whatever `python` is on PATH.
PYTHON="$ROOT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python

cd "$ROOT_DIR/validator"
"$PYTHON" validate.py "$TASK_DIR"
