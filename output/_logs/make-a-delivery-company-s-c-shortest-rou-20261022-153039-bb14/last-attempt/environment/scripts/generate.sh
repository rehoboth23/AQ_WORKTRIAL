#!/bin/bash
# Run at Docker build time to create benchmark data.
# Deletes itself and the reference implementation afterwards.
set -euo pipefail

cd /app

echo ">>> Generating benchmark graphs"
python3 scripts/gen_benchmark.py benchmark

echo ">>> Compiling reference implementation"
gcc -O2 -o ref_route scripts/ref_route.c -lm

echo ">>> Running reference to produce expected outputs"
mkdir -p benchmark/expected
> benchmark/baseline_relaxations.txt

prev_graph=""
while IFS=' ' read -r graph_name src dst; do
    graph_file="benchmark/${graph_name}.txt"
    expected_file="benchmark/expected/${graph_name}.out"

    # Run reference; stdout → path output, stderr → relax count
    path_out=$(./ref_route "$graph_file" "$src" "$dst" 2>/tmp/ref_err) || true
    relax=$(cat /tmp/ref_err)

    # Append to per-graph expected file
    echo "$path_out" >> "$expected_file"

    # Record baseline relaxation count for the first query of each graph
    if [ "$graph_name" != "$prev_graph" ]; then
        echo "${graph_name} ${relax}" >> benchmark/baseline_relaxations.txt
        prev_graph="$graph_name"
    fi
done < benchmark/queries.txt

echo ">>> Baseline relaxation counts:"
cat benchmark/baseline_relaxations.txt

echo ">>> Cleaning up reference and generator"
rm -f ref_route /tmp/ref_err
rm -f scripts/ref_route.c scripts/gen_benchmark.py scripts/generate.sh
rm -f benchmark/queries.txt

echo ">>> Benchmark generation complete"
