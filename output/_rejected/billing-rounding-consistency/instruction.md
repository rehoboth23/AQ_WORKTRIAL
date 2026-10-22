You maintain a Python billing module at `/app/billing/` that calculates invoices — subtotals, taxes, discounts, fees, and surcharges.

**Business rule that must hold everywhere in this module:** Every monetary amount must be rounded using round-half-up to 2 decimal places (standard business rounding: when a value is exactly halfway between two possibilities, it rounds away from zero).

**Problem:** Customers have reported incorrect amounts on invoices. Some monetary calculations in the module produce wrong results due to rounding that is inconsistent with the round-half-up rule. Find and fix every place where a monetary amount is rounded inconsistently.

**Constraints:**
1. All existing calculations that are already correct must remain correct.
2. Do not remove or rename any public function or change its parameter signatures.

**Running invoices:**
```
python /app/run_invoice.py <invoice_id>
```

The module and its runner are under `/app/`.
