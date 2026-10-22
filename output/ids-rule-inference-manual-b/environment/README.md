# Sentinel-7 IDS — Flow Log Documentation

## Overview

This directory contains network flow records processed by the retired
Sentinel-7 intrusion detection system (IDS).  The system has been
decommissioned, but for compliance auditing we must reproduce its exact
decisions on new flows.

Each flow was classified as either **`flag`** (suspicious — the IDS flagged
it for review) or **`pass`** (allowed — no action taken).

The training file `flows_train.csv` contains approximately 40 000 labelled
flows.  The IDS configuration was never exported; its rules have to be
recovered from these labels.

---

## Field Definitions

| Field       | Description                                                        |
|-------------|--------------------------------------------------------------------|
| `flow_id`   | Unique identifier for the flow                                     |
| `timestamp` | ISO 8601 UTC timestamp, e.g. `2024-07-15T14:30:22Z`                |
| `src_ip`    | Source IP address                                                  |
| `src_port`  | Source port number (0-65535)                                       |
| `dst_ip`    | Destination IP address                                             |
| `dst_port`  | Destination port number (0-65535)                                  |
| `protocol`  | Transport protocol: `TCP` or `UDP`                                 |
| `bytes`     | Total bytes transferred in the flow                                |
| `packets`   | Number of packets in the flow                                      |
| `decision`  | IDS decision: `flag` or `pass` (present only in the training file) |

---

## Conventions

- **Timestamps**: all timestamps in the CSV are UTC, formatted as ISO 8601
  with a `Z` suffix.
- **Sensor location**: the sensor ran in the **America/Chicago** timezone,
  which observes daylight saving time.  Anything the IDS did by time of day
  used the sensor's local clock, not UTC.
- **Context**: a decision can depend on other flows from the same source,
  not only on the flow being decided.
- **Decisions**: `flag` means the flow was flagged as suspicious; `pass`
  means it was allowed.

---

## Public Test Set

A small set of 500 unlabelled flows is provided in `public_test/flows.csv`
with expected decisions in `public_test/expected.csv`.  The
`public_test/verify.sh` script checks your implementation against these
common-path cases.  The full evaluation uses other flows, including flows
close to every decision boundary.
