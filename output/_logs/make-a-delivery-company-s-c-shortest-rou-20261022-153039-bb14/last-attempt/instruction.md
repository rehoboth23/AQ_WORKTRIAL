# SpeedyDeliver Route Library — Implementation Task

The SpeedyDeliver route-planning C library used a naive O(V²) Dijkstra. It worked correctly but was too slow for production. The old algorithm has been removed from `route.c`; only the infrastructure (graph loading, memory management, CLI) remains. Your job is to implement `route_find` so the library is at least 10× faster while producing identical results.

## What you must implement

Replace the stub in `route.c` with a working shortest-route algorithm. The public API declared in `route.h` must remain unchanged:

- `route_find(g, src, dst, &path, &len)` — returns 0 on success, −1 if unreachable
- `route_relaxations()` — distance-value comparison count from the last `route_find`
- `route_last_cost()` — total cost from the last successful `route_find`
- `route_load` / `route_free` — unchanged

## Requirements

1. **Performance**: `route_relaxations()` must return ≤ baseline_count / 10 on each benchmark graph. See `benchmark/baseline_relaxations.txt` for the baseline counts.

2. **Correct output**: Output on the benchmark graphs must be byte-identical to the frozen expected files in `benchmark/expected/`.

3. **Tie-breaking**: Among equal-cost routes, the one whose node-id sequence is lexicographically smallest is returned. Comparison is element-by-element from the source; a shorter sequence that is a prefix of a longer one is considered smaller. See `route.h` for the full rule. Because zero-weight edges can create equal-cost paths that are discovered after the destination is first extracted from the priority queue, the algorithm must continue exploring all reachable nodes until the queue is empty — do not terminate early when the destination is extracted.

4. **Unreachable destinations**: Print `unreachable` followed by a newline, exit code 1. See `README.md`.

5. **Relaxation counter semantics**: Only distance-value comparisons are counted — any comparison where at least one operand is a node's current shortest-path distance estimate. Comparisons of node identifiers, array indices, or path arrays for tie-breaking are NOT counted. See `route.h` for the precise definition.

6. **Self-loops**: Edges from a node to itself (u→u) with non-negative weight are valid graph edges and must not cause infinite loops or incorrect results.

7. **Trivial queries**: When src equals dst, `route_find` must return success with the path consisting of only [src] and total cost 0.

## Key files

- `route.h` — public API, tie-breaking rule, relaxation-counter definition
- `route.c` — file you must modify (currently a stub)
- `main.c` — CLI (`./route GRAPH_FILE SRC DST`), do not modify
- `Makefile` — build with `make`
- `README.md` — output format, graph format, API summary
- `benchmark/` — benchmark graphs and expected outputs
- `run_tests.sh` — public test script

## Output format

- **Reachable**: node ids space-separated, then a single space, then the total cost as a decimal integer, then a newline. Exit code 0.
- **Unreachable**: the exact string `unreachable` then a newline. Exit code 1.

## Building and testing

```sh
make
bash run_tests.sh
```

The public test script checks output against frozen expected files and verifies the 10× relaxation target.

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
