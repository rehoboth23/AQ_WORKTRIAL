# Bonded Warehouse Excise-Duty Return Procedure Manual

**Document ID:** PROC-WH1-EXC-2024  
**Effective:** 1 January 2024  
**Applies to:** Bonded warehouse WH1

---

## 1. Purpose and Scope

This manual defines the procedure for filing the month-end excise-duty return for bonded warehouse WH1. All duty calculations and filing steps must follow this procedure exactly. Deviations from this procedure may result in incorrect duty assessments and audit findings.

---

## 2. Commodity Duty Rates

Duty rates are published in the commodities schedule and may be updated periodically. The current rates are:

| Commodity | Duty Rate | Unit |
|-----------|-----------|------|
| Spirits   | $25.00    | L    |
| Tobacco   | $50.00    | kg   |
| Beer      | $5.00     | L    |
| Wine      | $15.00    | L    |

The commodities schedule is available from the ERP service at `GET http://localhost:5001/commodities`.

---

## 3. Duty Calculation Rules

### 3.1 Sales to Customers

Sales to customers are dutiable events. **Duty is calculated using the rate published in the commodities schedule.** The `unit_price` field in movement records records the commercial value and is not used for duty calculation.

    Duty = quantity × duty_rate

The duty rate must be obtained from the `/commodities` endpoint of the ERP service, not from the movement record.

### 3.2 Inter-Site Bonded Transfers

Movements between bonded sites — where both the origin site code and the destination site code begin with `WH` — are not duty events. No duty is calculated for these transfers. Such movements are **excluded from the duty return entirely**; they do not appear in `duty_lines`.

A transfer is identified by `type = "transfer"` and verified by checking that both `site_from` and `site_to` start with `"WH"`.

### 3.3 Customer Returns

Returns from customers are credited in the month they are received. The credit is calculated at the duty rate from the commodities schedule.

    Credit = −(quantity × duty_rate)

Return credits appear as `duty_lines` entries with `duty_type = "return"` and a negative `duty` value.

### 3.4 Evaporation Losses

Evaporation losses are subject to a tolerance of **0.5% of the opening stock** for the commodity at the site.

    Tolerance = opening_balance × 0.005

**Losses within tolerance (inclusive of the limit) carry no duty.** Such losses are excluded from the duty return entirely; they do not appear in `duty_lines`.

For losses **exceeding tolerance**, only the excess quantity is dutiable:

    Excess = loss_quantity − tolerance  
    Duty   = excess × duty_rate

Over-tolerance loss entries appear as `duty_lines` entries with `duty_type = "loss_over_tolerance"`.

**Worked example:**  
Opening stock of spirits at WH1 is 1,000 L.  
Tolerance = 1,000 × 0.005 = 5 L.  
An evaporation loss of 8 L is recorded. Since 8 > 5, the excess is 8 − 5 = 3 L.  
Duty = 3 × $25.00 = **$75.00**.

### 3.5 Movement Type Identification

Each movement record has a `type` field:

| Type       | Meaning                     |
|------------|-----------------------------|
| `sale`     | Sale to a customer          |
| `transfer` | Inter-site bonded transfer  |
| `return`   | Return from a customer      |
| `loss`     | Evaporation loss            |

A movement is exactly one type. Apply the rule for that type only.

The opening stock for each commodity at each site is obtained from the stock ledger service at `GET http://localhost:5002/entries?month=YYYY-MM`.

---

## 4. Filing Process

### 4.1 Two-Step Submission

Filing is a two-step process. Both steps must be completed for the return to be considered filed.

**Step 1 — Submit the return:**

    POST http://localhost:5003/submit

Request body (JSON):

```json
{
  "request_id": "RET-2024-03",
  "month": "2024-03",
  "duty_lines": [ ... ],
  "total_duty": 6972.50
}
```

Successful response (200 OK):

```json
{
  "reference": "REF-2024-03-abcdef12"
}
```

**Step 2 — Confirm the submission:**

    POST http://localhost:5003/confirm

Request body (JSON):

```json
{
  "reference": "REF-2024-03-abcdef12",
  "request_id": "RET-2024-03"
}
```

Successful response (200 OK):

```json
{
  "confirmation_code": "CONF-2024-03-xyz45678"
}
```

**Step 3 — Archive the confirmation:**

After receiving the confirmation code, write the result to a JSON file:

    /app/returns/{month}/confirmation.json

The file must contain:

```json
{
  "confirmation_code": "CONF-2024-03-xyz45678",
  "reference": "REF-2024-03-abcdef12",
  "month": "2024-03",
  "filed_at": "2024-03-31T23:59:59"
}
```

The `filed_at` field should contain an ISO 8601 timestamp of when the confirmation was received.

### 4.2 Retry and Idempotency

If the portal returns **HTTP 503** (Service Unavailable), retry the same request after a short wait (1 second). Use the **same `request_id`** on every retry of the same step.

The portal is idempotent only when the `request_id` is included. **A request without a `request_id` always creates a new submission.** The `request_id` must be included on **both the submit and confirm steps**, and on all retries of both steps.

Recommended retry limit: 5 attempts per step.

### 4.3 Finality

Submissions are final. Once confirmed, a return cannot be modified or withdrawn. All submissions are recorded in the portal's audit log, accessible at `GET http://localhost:5003/audit`.

---

## 5. Return Format

The `duty_lines` array contains one entry per dutiable movement:

```json
{
  "commodity": "spirits",
  "duty_type": "sale",
  "quantity": 100,
  "duty_rate": 25.00,
  "duty": 2500.00
}
```

Valid `duty_type` values:

| `duty_type`            | When used                          | Duty sign |
|------------------------|------------------------------------|-----------|
| `sale`                 | Sales to customers                 | Positive  |
| `return`               | Customer returns (credits)         | Negative  |
| `loss_over_tolerance`  | Evaporation losses exceeding limit | Positive  |

Transfers and within-or-at-tolerance losses do **NOT** appear in `duty_lines`.

The `total_duty` field is the **sum of all `duty_lines[].duty` values**, rounded to 2 decimal places.

---

## 6. Data Sources

| Source          | Endpoint                                          | Data                     |
|-----------------|---------------------------------------------------|--------------------------|
| ERP             | `GET http://localhost:5001/movements?month=YYYY-MM` | Movement records         |
| ERP             | `GET http://localhost:5001/commodities`             | Commodity duty rates     |
| Stock Ledger    | `GET http://localhost:5002/entries?month=YYYY-MM`   | Opening/closing balances |
| Filing Portal   | `POST http://localhost:5003/submit`                 | Submit return            |
| Filing Portal   | `POST http://localhost:5003/confirm`                | Confirm submission       |
| Filing Portal   | `GET http://localhost:5003/audit`                   | Audit log                |
| Filing Portal   | `GET http://localhost:5003/submissions`             | Submission records       |
