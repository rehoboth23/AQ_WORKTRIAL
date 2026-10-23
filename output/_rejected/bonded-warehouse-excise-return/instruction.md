# Bonded Warehouse WH1 - Month-End Excise-Duty Return

You are the duty accountant for bonded warehouse WH1. It is month-end: you must file the excise-duty return for March 2024. Three mock HTTP services run locally -- an ERP (movements and commodities), a stock ledger (opening balances, read-only), and a filing portal (two-step submission with retry). The in-house procedure manual at /app/docs/procedure.md defines every rule.

## What You Must Do

1. Read `/app/docs/procedure.md` thoroughly. It defines every rule for duty calculation and the filing process.
2. Fix the broken filing script at `/app/file_return.py` so it correctly calculates duty and files the return per the procedure manual.
3. Start the three local services with `/app/start_services.sh` (ERP on port 5001, stock ledger on 5002, filing portal on 5003).
4. Run the fixed script to file the return for March 2024.

## The Three Local Services

- **ERP** (port 5001): `GET http://localhost:5001/movements?month=YYYY-MM` returns movement records. `GET http://localhost:5001/commodities` returns the commodities schedule with duty rates.
- **Stock Ledger** (port 5002): `GET http://localhost:5002/entries?month=YYYY-MM` returns stock opening and closing balances. This data is read-only.
- **Filing Portal** (port 5003): Two-step filing: `POST /submit` then `POST /confirm`. Query with `GET /audit` and `GET /submissions`.

## The Broken Script

The script at `/app/file_return.py` has several known issues:

- It uses the `unit_price` from movement records to calculate duty. The procedure manual states that duty is calculated using the duty rate from the commodities schedule, not the commercial unit price.
- It treats all movement types as dutiable. The procedure manual states that inter-site bonded transfers and evaporation losses within tolerance are excluded from duty.
- It skips the confirmation step. Filing requires both a submit and a confirm call.
- It has no retry logic for HTTP 503, no `request_id` for idempotency, and does not archive the confirmation code.

## Key Points

- **The portal validates format only** -- it does not check whether your duty amounts are correct. A submission with wrong duty amounts will be accepted. You must follow the procedure manual to get the amounts right.
- **Practice data** at `/app/data/practice/returns/` shows completed returns for prior months. Practice movements and stock are at `/app/data/practice/months/`. Portal audit-log examples are at `/app/data/practice/portal_examples/`.
- **Submissions are final and audited** -- once confirmed, a return cannot be modified or resubmitted.
- Do not modify any file under `/app/data/` (the stock ledger and movement data are read-only).

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
