# Prior Authorization Queue Closeout

You must fix the prior authorization queue processor at `/app/process_queue.py` so it correctly processes every case in `/app/queue.json` according to the operating manual at `/app/manual.md`, submits each decision to the portal, and writes a correct audit log.

## What to do

1. Read `/app/manual.md` carefully. It defines the complete procedure, decision codes, reason codes, source-precedence rules, quantity-limit boundaries, and reason-code precedence.

2. Fix `/app/process_queue.py` so it implements every step in the manual, in the stated order.

3. Start the local services: `bash /app/services/start_services.sh`

4. Run the processor: `python3 /app/process_queue.py`

5. Verify with the public tests: `python3 /app/tests_public/run_public_tests.py`

## Interface

- **Entry point:** `python3 /app/process_queue.py` reads `/app/queue.json`, processes all cases, submits decisions to the portal, and writes `/app/audit.log`.

- **Portal submission:** `POST http://localhost:5004/submit` with JSON body `{case_id, decision_code, reason_code}`. Returns HTTP 201 on success.

- **Audit log:** `/app/audit.log` in JSON Lines format, one JSON object per line. Each entry must contain: `case_id`, `decision_code`, `reason_code`, `drug_id`, `patient_id`, `plan_tier`.

- **Decision codes:** `APPROVED`, `DENIED`.

- **Reason codes:** `MEETS_CRITERIA`, `STEP_THERAPY_NOT_MET`, `STEP_THERAPY_MET_VIA_PRESCRIBER`, `QUANTITY_LIMIT_EXCEEDED`, `QUANTITY_EXCEPTION`.

## Key points

- The manual is the sole authority for how decisions are made. Follow it exactly.
- Each case must appear exactly once in the audit log. Decisions are final: do not resubmit or revise a decision once submitted.
- Patient records under `/app/data/patients/` are read-only. Do not modify, delete, or create files in this directory.

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
