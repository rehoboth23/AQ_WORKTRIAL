You are helping a network operations team reproduce the decisions of their retired Sentinel-7 intrusion detection system (IDS) for compliance auditing. The IDS was decommissioned, but the team still needs to show that every flow it would process today gets the same flag/pass decision it would have gotten historically.

The only artefacts left are a CSV of about 40,000 labelled flows the IDS already processed and a README documenting the fields and conventions. The IDS rules themselves were never written down: you must recover them from the labelled data and implement a script that replicates the IDS decisions on new flows.

## Files

- `/app/README.md` — field definitions and conventions.
- `/app/flows_train.csv` — ~40,000 labelled flows. Columns: `flow_id,timestamp,src_ip,src_port,dst_ip,dst_port,protocol,bytes,packets,decision`.
- `/app/public_test/flows.csv` and `/app/public_test/expected.csv` — 500 flows with expected decisions, for checking common-path correctness.
- `/app/public_test/verify.sh` — runs your script against the 500 public flows.

## Task

Create `/app/decide.py` that reproduces the IDS decisions.

### Interface

1. Run as: `python3 /app/decide.py <input_csv_path>`
2. Input CSV header: `flow_id,timestamp,src_ip,src_port,dst_ip,dst_port,protocol,bytes,packets` (no `decision` column).
3. Timestamps are ISO 8601 UTC with a `Z` suffix, e.g. `2024-07-15T14:30:22Z`.
4. Output CSV to **stdout**: header `flow_id,decision`, one row per input flow, in the **same order as the input rows**.
5. Decisions: lowercase `flag` or `pass`.
6. Exit code 0 on success.
7. Must finish within 60 seconds on 2,000 flows.

### Requirements

- **Reproduce training decisions.** Every flow in `flows_train.csv` must get the decision it was labelled with. This is a compliance requirement.
- **Decisions on new flows must match the IDS exactly**, including flows right at any threshold, on either side of any range boundary, and where more than one rule could apply. The evaluation contains many such flows; the public test contains none of them.
- **Local time is the sensor's.** The sensor ran in America/Chicago, which observes daylight saving time; the CSV timestamps are UTC.
- **No network access** at runtime. Everything you need is in the image.

## Checking your work

Run `bash /app/public_test/verify.sh`. It checks common-path cases only.
