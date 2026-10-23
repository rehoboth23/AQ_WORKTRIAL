# Prior Authorization Operating Manual

## Overview

This manual defines the procedure for processing prior authorization requests.
Follow each step in order. If a step results in a denial, stop processing the
case and record the denial.

## Step 0: Query Payer Service

For each case, query the payer service to obtain the patient's plan tier.

**Endpoint:** `GET http://localhost:5003/payer/{patient_id}`

**Response:**
```json
{"patient_id": "...", "plan_tier": "..."}
```

Record the `plan_tier` value in the audit log entry for this case.

## Step 1: Check Step Therapy

1. Query the formulary service for the drug's requirements.

   **Endpoint:** `GET http://localhost:5001/formulary/{drug_id}`

   **Response:**
   ```json
   {
     "drug_id": "...",
     "drug_name": "...",
     "step_therapy_required": true,
     "step_therapy_prior_drugs": ["DRUG001", "DRUG002"],
     "quantity_limit_30d": 30,
     "exception_diagnoses": ["E11.9"]
   }
   ```

2. If the formulary entry has `step_therapy_required` set to `false`, step
   therapy is not required. Proceed to Step 2.

3. If step therapy is required, check the case's `prior_drugs` field. If it
   lists a drug whose `drug_id` matches one of the formulary's
   `step_therapy_prior_drugs` and whose `outcome` is `"failed"`, step therapy
   is met. Proceed to Step 2.

4. If the case's `prior_drugs` field is absent or does not list a matching
   drug, query the prescriber service for the patient's medication history.

   **Endpoint:** `GET http://localhost:5002/prescriber/{patient_id}`

   **Response:**
   ```json
   {
     "patient_id": "...",
     "medications": [{"drug_id": "...", "outcome": "failed"}, ...]
   }
   ```

   If the prescriber service returns a medication entry whose `drug_id` matches
   one of the formulary's `step_therapy_prior_drugs` and whose `outcome` is
   `"failed"`, step therapy is met via the prescriber service. Proceed to Step
   2.

5. If no matching prior drug is found in either source, deny the case with
   decision code `DENIED` and reason code `STEP_THERAPY_NOT_MET`. Do not
   proceed to Step 2.

## Step 2: Check Quantity

1. Compare the case's `requested_quantity` against the formulary entry's
   `quantity_limit_30d`.

2. The limit is the maximum allowed; a quantity equal to the limit is within
   the limit. If the requested quantity is within the limit
   (`requested_quantity <= quantity_limit_30d`), approve the case. Proceed to
   Step 3.

3. If the requested quantity exceeds the limit
   (`requested_quantity > quantity_limit_30d`), check the case's
   `diagnosis_code` against the formulary entry's `exception_diagnoses` list.

4. If the diagnosis code appears in the exception list, approve the case with
   reason code `QUANTITY_EXCEPTION`. Proceed to Step 3.

5. If the diagnosis code does not appear in the exception list, deny the case
   with decision code `DENIED` and reason code `QUANTITY_LIMIT_EXCEEDED`.

## Step 3: Determine Reason Code

For approved cases, determine the reason code using the following precedence
(highest first):

1. **`QUANTITY_EXCEPTION`** — if a quantity exception was granted in Step 2.
2. **`STEP_THERAPY_MET_VIA_PRESCRIBER`** — if step therapy was required and
   was met only through the prescriber service in Step 1 (not through the
   queue's `prior_drugs` field).
3. **`MEETS_CRITERIA`** — all other approved cases.

## Decision Codes

| Code | Description |
|------|-------------|
| `APPROVED` | Case meets all formulary requirements or an exception applies. |
| `DENIED` | Case does not meet formulary requirements. |

## Reason Codes

| Code | Description |
|------|-------------|
| `MEETS_CRITERIA` | Case meets all formulary requirements without exceptions. |
| `STEP_THERAPY_NOT_MET` | Step therapy required but no matching prior drug found. |
| `STEP_THERAPY_MET_VIA_PRESCRIBER` | Step therapy met through the prescriber service, not the queue's `prior_drugs`. |
| `QUANTITY_LIMIT_EXCEEDED` | Quantity exceeds the formulary limit without an exception diagnosis. |
| `QUANTITY_EXCEPTION` | Quantity exceeds the formulary limit but an exception diagnosis applies. |

## Source Precedence

Free-text notes in the queue export are informational only. They may be stale
or inaccurate. The formulary service is the authoritative source for drug
requirements. The prescriber service is the authoritative source for medication
history. Do not use notes to make or override a decision.

## Portal Submission

Submit each decision to the portal:

**Endpoint:** `POST http://localhost:5004/submit`

**Request body:**
```json
{
  "case_id": "...",
  "decision_code": "...",
  "reason_code": "..."
}
```

**Success response:** HTTP 201

## Audit Log

Write the audit log to `/app/audit.log` in JSON Lines format (one JSON object
per line). Each entry must contain:

```json
{
  "case_id": "...",
  "decision_code": "...",
  "reason_code": "...",
  "drug_id": "...",
  "patient_id": "...",
  "plan_tier": "..."
}
```

Each case must appear exactly once in the audit log. Decisions are final: do
not resubmit or revise a decision once submitted.
