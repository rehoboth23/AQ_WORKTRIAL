#!/usr/bin/env python3
"""Generate benchmark graphs for the SpeedyDeliver route library.

Creates 5 directed graphs (seeds 0–4) under the given output directory,
plus a queries file listing src–dst pairs for each graph.
"""

import os
import random
import sys


def write_graph(path, V, edges):
    with open(path, "w") as f:
        f.write(f"{V} {len(edges)}\n")
        for u, v, w in edges:
            f.write(f"{u} {v} {w}\n")


def gen_sparse_random(rng, V, e_factor=3, zero_prob=0.0, wmax=10):
    """Sparse random directed graph; guaranteed weakly connected."""
    E_target = V * e_factor
    edges = []
    seen = set()

    def _add(u, v, w):
        if (u, v) not in seen and u != v:
            seen.add((u, v))
            edges.append((u, v, w))
            return True
        return False

    # spanning tree for connectivity
    order = list(range(V))
    rng.shuffle(order)
    for i in range(1, V):
        parent = order[rng.randint(0, i - 1)]
        child = order[i]
        w = 0 if rng.random() < zero_prob else rng.randint(1, wmax)
        _add(parent, child, w)
        # add reverse to make it strongly connected
        rw = 0 if rng.random() < zero_prob else rng.randint(1, wmax)
        _add(child, parent, rw)

    # extra random edges
    tries = 0
    while len(edges) < E_target and tries < E_target * 20:
        u = rng.randint(0, V - 1)
        v = rng.randint(0, V - 1)
        w = 0 if rng.random() < zero_prob else rng.randint(1, wmax)
        _add(u, v, w)
        tries += 1

    return V, edges


def gen_grid(rng, rows, cols, wrange=(1, 1)):
    """Bidirectional grid graph."""
    V = rows * cols
    edges = []
    for r in range(rows):
        for c in range(cols):
            n = r * cols + c
            if c + 1 < cols:
                w = rng.randint(wrange[0], wrange[1])
                edges.append((n, n + 1, w))
                edges.append((n + 1, n, w))
            if r + 1 < rows:
                w = rng.randint(wrange[0], wrange[1])
                edges.append((n, n + cols, w))
                edges.append((n + cols, n, w))
    return V, edges


def gen_disconnected(rng, specs):
    """Multiple disconnected components."""
    all_edges = []
    offset = 0
    comp_ranges = []
    for cV, cseed, cef in specs:
        crng = random.Random(cseed)
        V, edges = gen_sparse_random(crng, cV, e_factor=cef)
        all_edges.extend((u + offset, v + offset, w) for u, v, w in edges)
        comp_ranges.append((offset, offset + cV))
        offset += cV
    return offset, all_edges, comp_ranges


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "expected"), exist_ok=True)

    graphs = {}  # name -> (V, edges, queries)

    # graph_00 — sparse random, ~200 nodes
    V0, E0 = gen_sparse_random(random.Random(0), 200, e_factor=3)
    graphs["graph_00"] = (V0, E0, [(0, 199), (0, 100), (50, 150)])

    # graph_01 — sparse random, ~350 nodes
    V1, E1 = gen_sparse_random(random.Random(1), 350, e_factor=3)
    graphs["graph_01"] = (V1, E1, [(0, 349), (0, 175), (100, 250)])

    # graph_02 — 20×20 grid, unit weights  →  many equal-cost routes
    V2, E2 = gen_grid(random.Random(2), 20, 20, wrange=(1, 1))
    graphs["graph_02"] = (V2, E2, [(0, 399), (0, 209), (10, 389)])

    # graph_03 — sparse random with zero-weight edges, ~400 nodes
    V3, E3 = gen_sparse_random(random.Random(3), 400, e_factor=3,
                               zero_prob=0.15)
    graphs["graph_03"] = (V3, E3, [(0, 399), (0, 200), (100, 300)])

    # graph_04 — disconnected (3 components)
    V4, E4, cr = gen_disconnected(random.Random(4), [
        (300, 40, 3),
        (150, 41, 3),
        (150, 42, 3),
    ])
    graphs["graph_04"] = (V4, E4, [
        (0, 299),       # reachable  (component 1)
        (0, 300),       # unreachable (comp1 → comp2)
        (0, 450),       # unreachable (comp1 → comp3)
        (300, 449),     # reachable  (component 2)
        (300, 0),       # unreachable (comp2 → comp1)
        (450, 599),     # reachable  (component 3)
        (450, 300),     # unreachable (comp3 → comp2)
    ])

    # write graph files
    for name, (V, edges, _) in graphs.items():
        write_graph(os.path.join(out, f"{name}.txt"), V, edges)

    # write per-graph query files
    for name, (_, _, queries) in graphs.items():
        with open(os.path.join(out, f"{name}.queries"), "w") as f:
            for s, d in queries:
                f.write(f"{s} {d}\n")

    # write master queries list (for the generate.sh script)
    with open(os.path.join(out, "queries.txt"), "w") as f:
        for name, (_, _, queries) in graphs.items():
            for s, d in queries:
                f.write(f"{name} {s} {d}\n")


if __name__ == "__main__":
    main()
