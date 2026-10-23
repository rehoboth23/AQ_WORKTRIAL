You are porting a legacy Tcl/Tk loan-application screen to a Flask web application. The original Tcl source is at `/app/loanapp.tcl`. A starter Flask app exists at `/app/webapp.py` but contains errors. Practice transcripts of the old screen's behaviour are in `/app/transcripts/`.

## Job

Fix `/app/webapp.py` so the Flask web app produces identical behaviour to the Tcl source. Read the Tcl source carefully — it defines every validation rule, the repayment calculation algorithm, and the database interaction logic.

## API Endpoints

### POST /api/calculate

Accepts form fields: `applicant_name`, `loan_amount`, `interest_rate`, `term_months`, `start_date` (all as strings).

On validation failure: returns HTTP 200 with JSON `{"valid": false, "error": "<message>"}` with exactly one error message.

On success: returns HTTP 200 with JSON:
```json
{
  "valid": true,
  "monthly_payment": <float>,
  "total_repayment": <float>,
  "total_interest": <float>,
  "schedule": [
    {
      "instalment_no": <int>,
      "payment_date": "DD/MM/YYYY",
      "payment": <float>,
      "principal": <float>,
      "interest": <float>,
      "balance": <float>
    }
  ],
  "display": {
    "monthly_payment": "$X,XXX.XX",
    "total_repayment": "$X,XXX.XX",
    "total_interest": "$X,XXX.XX",
    "interest_rate": "X.XX%",
    "start_date": "DD/MM/YYYY"
  }
}
```

### POST /api/save

Accepts same fields as `/api/calculate` plus optional `id`. Validates and calculates the repayment. INSERTs a new application row (or UPDATEs if `id` is provided), then DELETEs old schedule entries and INSERTs new ones. Returns HTTP 200 with `{"id": <int>}`.

### POST /api/delete/\<id\>

Without `confirmed=true`: returns HTTP 200 with `{"message": "Confirm deletion of application #<id>?"}`. The application and its schedule entries remain.

With `confirmed=true`: DELETEs FROM `schedule_entries` WHERE `application_id=<id>`, then DELETEs FROM `applications` WHERE `id=<id>`. Returns HTTP 200 with `{"message": "Application #<id> deleted."}`.

### GET /api/application/\<id\>

Returns HTTP 200 with application data and schedule from the database with display-formatted fields. Returns HTTP 404 with `{"error": "Application not found."}` if the id does not exist.

## Validation

Field priority order: `applicant_name` → `loan_amount` → `interest_rate` → `term_months` → `start_date`. When multiple fields fail, only the error for the first failing field (by this order) is returned. Within a single field, rules are checked in the order they appear in the Tcl source, and only the first failing rule's message is returned.

All validation rules and exact error message texts (including the trailing period) are defined in `/app/loanapp.tcl`.

The minimum start date for new loans is 01/01/2025.

## Repayment Calculation

Your implementation must produce identical figures to the Tcl source, including the rounding of every intermediate value. The monthly payment is computed as `format("%.2f", principal × monthly_rate / (1 − (1+monthly_rate)^(−term)))` where `monthly_rate = annual_rate/100/12`.

The schedule is computed per instalment: interest is rounded to 2 decimal places, principal is rounded to 2 decimal places (except the last instalment where principal equals the remaining balance), and the balance is rounded after each step — all using `format("%.2f")` semantics. Including the handling of the last instalment (principal = remaining balance, payment recalculated).

Total repayment equals the sum of all instalment payments. Total interest equals the sum of all interest components.

Payment dates use the Tcl source's `add_months` function, which adjusts the day for months with fewer days (e.g., 31 January → 28 February).

## Database

Saved applications must be stored in the `applications` table with amounts as integer cents, interest rate as integer basis points, and dates as DD/MM/YYYY text. Schedule entries must be stored in the `schedule_entries` table alongside the application row. Do not modify `/app/schema.sql` or create new tables.

## Display Formatting

- Currency amounts: `$X,XXX.XX` (comma thousand separator, two decimal places, dollar sign)
- Interest rate: `X.XX%` (always two decimal places, percent sign)
- Dates: `DD/MM/YYYY`

## Practice Transcripts

Recorded transcripts of the old screen's behaviour are in `/app/transcripts/`. Public tests are available in `/app/tests_public/`.

Do not modify `/app/schema.sql`, `/app/loanapp.tcl`, or anything under `/tests`. Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
