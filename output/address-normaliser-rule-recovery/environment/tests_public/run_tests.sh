#!/bin/bash
# Run public tests for the address normaliser
set -euo pipefail

NORMALISE="/app/normalise.py"
PAIRS="$(dirname "$0")/pairs.tsv"

if [ ! -f "$NORMALISE" ]; then
    echo "ERROR: normalise.py not found at $NORMALISE" >&2
    exit 1
fi

if [ ! -f "$PAIRS" ]; then
    echo "ERROR: pairs.tsv not found at $PAIRS" >&2
    exit 1
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Extract the "before" column (field 1) and the "after" column (field 2)
cut -f1 "$PAIRS" > "$TMPDIR/input.txt"
cut -f2 "$PAIRS" > "$TMPDIR/expected.txt"

# Run normalise.py via stdin
python3 "$NORMALISE" < "$TMPDIR/input.txt" > "$TMPDIR/actual.txt"

# Also verify --input/--output flags work
python3 "$NORMALISE" --input "$TMPDIR/input.txt" --output "$TMPDIR/actual_cli.txt"
if ! diff -q "$TMPDIR/actual.txt" "$TMPDIR/actual_cli.txt" > /dev/null 2>&1; then
    echo "WARNING: stdin and --input/--output produced different results"
fi

# Compare line by line
PASS=0
FAIL=0
TOTAL=0

exec 3< "$TMPDIR/actual.txt"
exec 4< "$TMPDIR/expected.txt"

while IFS= read -r actual <&3 && IFS= read -r expected <&4; do
    TOTAL=$((TOTAL + 1))
    if [ "$actual" = "$expected" ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL [$TOTAL]: expected='$expected' got='$actual'"
    fi
done

exec 3<&-
exec 4<&-

echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
echo "All public tests passed!"
