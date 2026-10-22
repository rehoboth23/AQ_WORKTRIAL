#!/usr/bin/env bash
# Start N copies of the pipeline on one batch; the ledger's per-topic locks split the topics.
# Usage: bash scripts/run-batch.sh <topics-file> <batch-id> <copies> [waves e.g. 3,7]
# Each copy logs to output/_batches/<batch-id>/copies/<n>.log. Resume later with:
#   bash scripts/pipeline.sh --resume <batch-id> [--waves ...]   (one or more copies)
set -euo pipefail
[ $# -ge 3 ] || { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
TOPICS="$1"; BATCH="$2"; COPIES="$3"; WAVES="${4:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
export PATH="$HOME/.docker/bin:$PATH"
mkdir -p "$ROOT_DIR/output/_batches/$BATCH/copies"
for i in $(seq 1 "$COPIES"); do
    ARGS=(--topics "$TOPICS" --batch-id "$BATCH")
    [ -n "$WAVES" ] && ARGS+=(--waves "$WAVES")
    nohup bash "$SCRIPT_DIR/pipeline.sh" "${ARGS[@]}" > "$ROOT_DIR/output/_batches/$BATCH/copies/$i.log" 2>&1 &
    echo "copy $i: pid $!"
    sleep 2
done
echo "logs: output/_batches/$BATCH/copies/   report: output/_reports/$BATCH.md   dashboard: jobs/dashboard.html"
