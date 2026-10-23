#!/bin/bash
# Public test script — checks output against frozen expected files
# and verifies the 10× relaxation-count target.
set -euo pipefail

cd /app

echo "=== Building ==="
make clean >/dev/null 2>&1
make >/dev/null 2>&1

PASS=0
FAIL=0

check() {
    local label="$1"
    if [ "$2" = "0" ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $label"
    fi
}

# ---- 1. Output correctness on benchmark graphs ----------------------

echo "=== Checking output against frozen expected files ==="

for gfile in benchmark/graph_*.txt; do
    name=$(basename "$gfile" .txt)
    expected="benchmark/expected/${name}.out"

    if [ ! -f "$expected" ]; then
        echo "  SKIP: no expected file for $name"
        continue
    fi

    # Read queries from expected file by replaying the same queries.
    # We store queries in a sidecar; if missing, skip.
    qfile="benchmark/${name}.queries"
    if [ ! -f "$qfile" ]; then
        echo "  SKIP: no query file for $name"
        continue
    fi

    actual_tmp=$(mktemp)
    while IFS=' ' read -r src dst; do
        ./route "$gfile" "$src" "$dst" >> "$actual_tmp" 2>/dev/null || true
    done < "$qfile"

    if diff -q "$actual_tmp" "$expected" >/dev/null 2>&1; then
        check "$name output" 0
    else
        check "$name output" 1
        diff "$actual_tmp" "$expected" | head -5
    fi
    rm -f "$actual_tmp"
done

# ---- 2. Relaxation count ≤ baseline / 10 ----------------------------

echo "=== Checking relaxation counts ==="

if [ -f benchmark/baseline_relaxations.txt ]; then
    while IFS=' ' read -r name baseline; do
        gfile="benchmark/${name}.txt"
        qfile="benchmark/${name}.queries"

        if [ ! -f "$qfile" ]; then
            echo "  SKIP: no query file for $name"
            continue
        fi

        # Use first query for the relaxation-count check
        first_query=$(head -1 "$qfile")
        src=$(echo "$first_query" | cut -d' ' -f1)
        dst=$(echo "$first_query" | cut -d' ' -f2)

        # Run route; capture exit code
        set +e
        output=$(./route "$gfile" "$src" "$dst" 2>&1)
        rc=$?
        set -e

        # We need route_relaxations — call a tiny helper if the binary
        # supports it.  Since the CLI does not expose the counter,
        # we compile a small test program.
        cat > /tmp/test_relax.c <<'CEOF'
#include <stdio.h>
#include <stdlib.h>
#include "route.h"
int main(int argc, char** argv) {
    if (argc < 4) return 2;
    RouteGraph* g = route_load(argv[1]);
    if (!g) return 2;
    int src = atoi(argv[2]), dst = atoi(argv[3]);
    int* path = NULL; int plen = 0;
    route_find(g, src, dst, &path, &plen);
    printf("%ld\n", route_relaxations());
    free(path);
    route_free(g);
    return 0;
}
CEOF
        gcc -O2 -o /tmp/test_relax /tmp/test_relax.c route.o -I. 2>/dev/null
        if [ -x /tmp/test_relax ]; then
            agent_count=$(/tmp/test_relax "$gfile" "$src" "$dst" 2>/dev/null || echo "999999999")
        else
            agent_count="999999999"
        fi

        threshold=$((baseline / 10))
        if [ "$threshold" -le 0 ]; then threshold=1; fi
        if [ "$agent_count" -le "$threshold" ]; then
            check "$name relaxations ($agent_count <= $threshold)" 0
        else
            check "$name relaxations ($agent_count > $threshold)" 1
        fi
    done < benchmark/baseline_relaxations.txt
fi

# ---- Summary --------------------------------------------------------

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
