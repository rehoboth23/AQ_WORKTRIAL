#!/usr/bin/env bash
# Run the pipeline on 5 randomly picked seed cards, 5 copies in parallel, with the dashboard up.
# Usage: bash scripts/run-five.sh [batch-id]            (DRY_RUN=1 prints the plan and exits)
#   Settings pass through as environment variables, e.g. MAX_REPAIR_ROUNDS=5 BAND_SLOTS=3 bash scripts/run-five.sh
# Picks 5 of scripts/seeds/*.yaml at random, writes them to output/_batches/<batch>/topics.txt, starts
# scripts/dashboard.sh in the background (jobs/dashboard.html, opened in the browser on macOS), starts the
# copies with scripts/run-batch.sh, waits for them, writes the batch report, then stops the dashboard.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"
BATCH="${1:-five-$(date +%H%M%S)}"
COPIES=5
export PATH="$HOME/.docker/bin:$PATH"
export BAND_SLOTS="${BAND_SLOTS:-3}"

[ -f .env ] || { echo "no .env (copy .env.example and fill in the key and endpoint)" >&2; exit 1; }
if [ "${DRY_RUN:-0}" != "1" ] && ! docker info >/dev/null 2>&1; then
    echo "Docker is not running" >&2; exit 1
fi

# 5 random cards (macOS has no shuf: sort by a random key).
mkdir -p "output/_batches/$BATCH"
TOPICS="output/_batches/$BATCH/topics.txt"
ls scripts/seeds/*.yaml | awk 'BEGIN{srand()} {print rand() "\t" $0}' | sort -n | cut -f2 | head -n 5 \
    | sed 's|^scripts/seeds/|@seeds/|' > "$TOPICS"
echo "batch $BATCH, topics:"; sed 's/^/  /' "$TOPICS"

if [ "${DRY_RUN:-0}" = "1" ]; then
    echo "dry run: would start the dashboard and $COPIES copies of: bash scripts/run-batch.sh $TOPICS $BATCH $COPIES"
    exit 0
fi

# Dashboard in the background for as long as this script runs, unless one is already running.
DASH=""
if pgrep -f "scripts/dashboard.sh" >/dev/null 2>&1; then
    echo "dashboard loop already running; leaving it as it is"
else
    bash scripts/dashboard.sh 15 > /dev/null 2>&1 &
    DASH=$!
    trap '[ -n "$DASH" ] && kill "$DASH" 2>/dev/null || true' EXIT
fi
sleep 3
echo "dashboard: $ROOT_DIR/jobs/dashboard.html (reloads itself)"
command -v open >/dev/null 2>&1 && open "jobs/dashboard.html" || true

bash scripts/run-batch.sh "$TOPICS" "$BATCH" "$COPIES"

# Wait for every copy of this batch to exit (they share the ledger; Ctrl-C here leaves them running).
echo "waiting for the batch (Ctrl-C stops only this wait; resume later with: bash scripts/pipeline.sh --resume $BATCH)"
while pgrep -f "pipeline.py --topics .* --batch-id $BATCH" >/dev/null 2>&1; do
    sleep 30
done
bash scripts/pipeline.sh --report "$BATCH" >/dev/null 2>&1 || true
echo "done. report: output/_reports/$BATCH.md   verdicts: output/*/VERDICT.md, output/_rejected/*/VERDICT.md"
