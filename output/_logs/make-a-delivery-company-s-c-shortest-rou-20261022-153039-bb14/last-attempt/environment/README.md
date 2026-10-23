# SpeedyDeliver Route Library

A C library for computing shortest routes in directed graphs with
non-negative integer edge weights (including zero).

## Building

```sh
make
```

This produces the `route` executable.

## Usage

```sh
./route GRAPH_FILE SRC DST
```

- `GRAPH_FILE`: path to a graph text file
- `SRC`: source node id (integer, 0-based)
- `DST`: destination node id (integer, 0-based)

### Output

- **Reachable**: the node ids of the shortest route, space-separated,
  followed by a single space and the total cost as a decimal integer,
  followed by a newline.  Exit code 0.

  Example: `0 1 3 7` followed by a space, the cost, and a newline.

- **Unreachable**: the exact string `unreachable` followed by a newline.
  Exit code 1.

## Graph File Format

```
V E
u1 v1 w1
u2 v2 w2
...
```

- `V` — number of vertices (ids 0 … V−1)
- `E` — number of directed edges
- Each edge line: source `u`, target `v`, non-negative weight `w`

## C API

See `route.h` for full documentation.  Summary:

| Function | Description |
|---|---|
| `route_load(filename)` | Load a graph from file |
| `route_free(g)` | Free a loaded graph |
| `route_find(g, src, dst, &path, &len)` | Find shortest path; returns 0 on success, −1 if unreachable |
| `route_relaxations()` | Distance-value comparison count from last `route_find` |
| `route_last_cost()` | Total cost from last successful `route_find` |

## Tie-breaking

Among equal-cost routes, the one whose **node-id sequence is
lexicographically smallest** is returned.  See `route.h` for the
complete rule, including the prefix convention for paths of different
lengths.

## Relaxation counter

`route_relaxations()` counts **distance-value comparisons only** —
any comparison where at least one operand is a node's current
shortest-path distance estimate.  See `route.h` for the precise
definition and examples of what is and is not counted.

## Benchmark

Benchmark graphs and expected outputs live under `benchmark/`.

- `benchmark/graph_XX.txt` — graph files (seeds 0–4)
- `benchmark/expected/graph_XX.out` — expected output for each graph's queries
- `benchmark/baseline_relaxations.txt` — O(V²) relaxation counts per graph

## Running public tests

```sh
bash run_tests.sh
```

This checks output against the frozen expected files and verifies the
10× relaxation-count target on each benchmark graph.
