#!/usr/bin/env python3
"""Public-test checker: runs decide.py on public_test/flows.csv and
compares the output against public_test/expected.csv.

Usage:
    python3 /app/public_test/check.py
"""

import csv
import os
import subprocess
import sys

FLOWS    = '/app/public_test/flows.csv'
EXPECTED = '/app/public_test/expected.csv'
DECIDE   = '/app/decide.py'


def main() -> None:
    if not os.path.exists(DECIDE):
        print(f"FAIL: {DECIDE} not found.  Create decide.py first.")
        sys.exit(1)

    # Run decide.py on the public test flows
    result = subprocess.run(
        ['python3', DECIDE, FLOWS],
        capture_output=True, text=True, timeout=60,
    )

    if result.returncode != 0:
        print(f"FAIL: decide.py exited with code {result.returncode}")
        if result.stderr:
            print(f"stderr: {result.stderr[:1000]}")
        sys.exit(1)

    lines = result.stdout.strip().split('\n')
    if not lines or not lines[0]:
        print("FAIL: no output from decide.py")
        sys.exit(1)

    # Check header
    header = lines[0].strip()
    if header != 'flow_id,decision':
        print(f"FAIL: header should be 'flow_id,decision', got '{header}'")
        sys.exit(1)

    # Read expected decisions
    expected: dict[str, str] = {}
    with open(EXPECTED, newline='') as f:
        for row in csv.DictReader(f):
            expected[row['flow_id']] = row['decision']

    # Read input row order
    input_ids: list[str] = []
    with open(FLOWS, newline='') as f:
        for row in csv.DictReader(f):
            input_ids.append(row['flow_id'])

    # Parse actual output (preserve order)
    actual: dict[str, str] = {}
    actual_order: list[str] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(',')
        if len(parts) != 2:
            print(f"FAIL: malformed line: {line}")
            sys.exit(1)
        fid = parts[0].strip()
        decision = parts[1].strip()
        actual[fid] = decision
        actual_order.append(fid)

    # Row count
    if len(actual_order) != len(input_ids):
        print(f"FAIL: expected {len(input_ids)} output rows, "
              f"got {len(actual_order)}")
        sys.exit(1)

    # Row order
    if actual_order != input_ids:
        print("FAIL: output row order does not match input order")
        for i, (a, b) in enumerate(zip(actual_order, input_ids)):
            if a != b:
                print(f"  row {i}: output '{a}'  vs  input '{b}'")
                break
        sys.exit(1)

    # Decision correctness
    correct = 0
    wrong: list[tuple[str, str, str]] = []
    for fid in input_ids:
        exp = expected.get(fid, '')
        act = actual.get(fid, '')
        if act not in ('flag', 'pass'):
            print(f"FAIL: invalid decision '{act}' for flow {fid}")
            sys.exit(1)
        if act == exp:
            correct += 1
        else:
            wrong.append((fid, exp, act))

    total = len(input_ids)
    acc = correct / total if total else 0.0
    print(f"Public test accuracy: {correct}/{total} = {acc:.1%}")

    if wrong:
        print(f"Mismatches ({len(wrong)}):")
        for fid, exp, act in wrong[:10]:
            print(f"  flow {fid}: expected {exp}, got {act}")

    if acc == 1.0:
        print("PASS")
        sys.exit(0)
    else:
        print("FAIL")
        sys.exit(1)


if __name__ == '__main__':
    main()
