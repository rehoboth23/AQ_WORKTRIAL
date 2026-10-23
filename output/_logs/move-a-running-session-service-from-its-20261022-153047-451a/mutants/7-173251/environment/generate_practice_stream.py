#!/usr/bin/env python3
"""Generate the practice load stream (seed 1) at build time.

Writes /app/practice_stream.json and verifies minimum coverage of all
quirk dimensions.
"""

import json
import os
import sys

# allow importing loadgen from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loadgen import generate_stream


def verify_coverage(stream):
    """Assert the stream covers every quirk dimension at least 3 times."""
    creates = [op for op in stream if op["op"] == "create"]
    reads = [op for op in stream if op["op"] == "read"]
    writes = [op for op in stream if op["op"] == "update"]

    # TTL coverage
    for ttl in (300, 5, 2):
        n = sum(1 for c in creates if c["ttl"] == ttl)
        assert n >= 3, f"Not enough creates with ttl={ttl}: found {n}"

    # operation coverage
    assert len(reads) >= 3, f"Not enough reads: {len(reads)}"
    assert len(writes) >= 3, f"Not enough writes: {len(writes)}"

    # read-after-write pairs
    raw = 0
    for i in range(len(stream) - 1):
        a, b = stream[i], stream[i + 1]
        if (
            a["op"] == "update"
            and b["op"] == "read"
            and a.get("session_id") == b.get("session_id")
        ):
            raw += 1
    assert raw >= 3, f"Not enough read-after-write pairs: {raw}"

    # writes near migration
    migrate_seq = next(op["seq"] for op in stream if op["op"] == "migrate")
    near = sum(
        1
        for op in writes
        if abs(op["seq"] - migrate_seq) <= 100
    )
    assert near >= 3, f"Not enough writes near migration: {near}"

    print(
        f"Coverage OK: {len(creates)} creates, {len(reads)} reads, "
        f"{len(writes)} writes, {raw} read-after-write pairs, "
        f"{near} writes near migration"
    )


def main():
    stream = generate_stream(1, 10000)
    verify_coverage(stream)

    out = "/app/practice_stream.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(stream, f, indent=2, sort_keys=True)
    print(f"Generated {len(stream)} operations -> {out}")


if __name__ == "__main__":
    main()
