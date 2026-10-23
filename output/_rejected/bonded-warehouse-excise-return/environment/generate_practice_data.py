#!/usr/bin/env python3
"""Generate practice data for the bonded warehouse excise-duty return task.

Run once at Docker build time, then delete this script.
Creates 9 practice months of movements + stock + completed returns,
and 9 portal-example audit logs (3 per fault type).
"""
import json
import os
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DIR = "/app/data/practice"
MONTHS_DIR = os.path.join(BASE_DIR, "months")
RETURNS_DIR = os.path.join(BASE_DIR, "returns")
PORTAL_DIR = os.path.join(BASE_DIR, "portal_examples")

COMMODITIES = {
    "spirits": {"duty_rate": 25.00, "unit": "L", "unit_price": 12.50},
    "tobacco": {"duty_rate": 50.00, "unit": "kg", "unit_price": 35.00},
    "beer":    {"duty_rate": 5.00,  "unit": "L", "unit_price": 3.00},
    "wine":    {"duty_rate": 15.00, "unit": "L", "unit_price": 18.00},
}

DEFAULT_OPENING = {
    "spirits": 1000,
    "tobacco": 200,
    "beer": 2000,
    "wine": 500,
}

CUSTOMERS = ["ACME Corp", "Beta Inc", "Delta Ltd", "Gamma LLC"]

# ---------------------------------------------------------------------------
# Practice month definitions
# ---------------------------------------------------------------------------
# Each entry: (month, loss_level, has_transfers, has_returns,
#              loss_commodity, loss_opening, loss_qty)
#
# loss_level: "within" | "at_limit" | "over"
# at_limit months straddle 0.5% (0.48–0.49% just within, 0.51% just over)
# but never land exactly on 0.5%.
PRACTICE_DEFS = [
    # within × sales_only
    ("2024-01", "within", False, False, "spirits", 1000, 3),
    # at_limit × plus_transfers  (0.49% — just within)
    ("2024-02", "at_limit", True, False, "spirits", 1000, 4.9),
    # over × plus_transfers + plus_returns
    ("2024-04", "over", True, True, "wine", 500, 4),
    # over × plus_returns
    ("2024-05", "over", False, True, "spirits", 1000, 8),
    # within × plus_returns
    ("2024-06", "within", False, True, "beer", 2000, 5),
    # within × plus_transfers
    ("2024-07", "within", True, False, "tobacco", 200, 0.5),
    # at_limit × sales_only  (0.48% — just within)
    ("2024-08", "at_limit", False, False, "spirits", 1000, 4.8),
    # at_limit × plus_transfers + plus_returns  (0.51% — just over)
    ("2024-09", "at_limit", True, True, "spirits", 1000, 5.1),
    # over × sales_only
    ("2024-10", "over", False, False, "spirits", 1000, 7),
]

# Sales quantities for each month (all four commodities always present)
SALES_TABLE = {
    "2024-01": [("spirits", 100), ("tobacco", 50), ("beer", 200), ("wine", 80)],
    "2024-02": [("spirits", 80),  ("tobacco", 30), ("beer", 150), ("wine", 60)],
    "2024-04": [("spirits", 90),  ("tobacco", 40), ("beer", 180), ("wine", 70)],
    "2024-05": [("spirits", 120), ("tobacco", 60), ("beer", 250), ("wine", 90)],
    "2024-06": [("spirits", 110), ("tobacco", 45), ("beer", 220), ("wine", 75)],
    "2024-07": [("spirits", 95),  ("tobacco", 55), ("beer", 190), ("wine", 65)],
    "2024-08": [("spirits", 85),  ("tobacco", 35), ("beer", 160), ("wine", 55)],
    "2024-09": [("spirits", 75),  ("tobacco", 25), ("beer", 140), ("wine", 50)],
    "2024-10": [("spirits", 105), ("tobacco", 65), ("beer", 230), ("wine", 85)],
}

# Transfer details per month
TRANSFERS_TABLE = {
    "2024-02": [("beer", 40, "WH1", "WH2")],
    "2024-04": [("spirits", 30, "WH1", "WH2")],
    "2024-07": [("tobacco", 10, "WH1", "WH2")],
    "2024-09": [("wine", 20, "WH1", "WH2")],
}

# Return details per month
RETURNS_TABLE = {
    "2024-04": [("tobacco", 5, "ACME Corp")],
    "2024-05": [("spirits", 10, "Beta Inc")],
    "2024-06": [("beer", 15, "Delta Ltd")],
    "2024-09": [("beer", 10, "Gamma LLC")],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def tolerance(opening):
    return opening * 0.005


def compute_duty_lines(movements, stock_entries):
    """Compute duty lines following the procedure manual rules."""
    opening = {}
    for entry in stock_entries:
        key = (entry["commodity"], entry["site"])
        opening[key] = entry["opening_balance"]

    duty_lines = []
    for mov in movements:
        mtype = mov["type"]
        commodity = mov["commodity"]
        qty = mov["quantity"]
        site = mov.get("site", "WH1")
        dr = COMMODITIES[commodity]["duty_rate"]

        if mtype == "sale":
            duty_lines.append({
                "commodity": commodity,
                "duty_type": "sale",
                "quantity": qty,
                "duty_rate": dr,
                "duty": round(qty * dr, 2),
            })
        elif mtype == "transfer":
            # Excluded entirely
            pass
        elif mtype == "return":
            duty_lines.append({
                "commodity": commodity,
                "duty_type": "return",
                "quantity": qty,
                "duty_rate": dr,
                "duty": round(-(qty * dr), 2),
            })
        elif mtype == "loss":
            tol = tolerance(opening.get((commodity, site), 0))
            if qty <= tol:
                # Within or at tolerance — excluded
                pass
            else:
                excess = round(qty - tol, 4)
                duty_lines.append({
                    "commodity": commodity,
                    "duty_type": "loss_over_tolerance",
                    "quantity": round(excess, 2),
                    "duty_rate": dr,
                    "duty": round(excess * dr, 2),
                })

    total_duty = round(sum(dl["duty"] for dl in duty_lines), 2)
    return duty_lines, total_duty


def generate_month(month, loss_level, has_transfers, has_returns,
                   loss_commodity, loss_opening, loss_qty):
    """Generate movements, stock entries, and completed return for one month."""
    mov_id = 1
    movements = []
    day = 5

    # --- Sales ---
    for commodity, qty in SALES_TABLE[month]:
        movements.append({
            "id": f"M{mov_id:03d}",
            "date": f"{month}-{day:02d}",
            "type": "sale",
            "commodity": commodity,
            "quantity": qty,
            "unit_price": COMMODITIES[commodity]["unit_price"],
            "site": "WH1",
            "customer": CUSTOMERS[(mov_id - 1) % len(CUSTOMERS)],
        })
        mov_id += 1
        day += 3

    # --- Transfers ---
    if has_transfers:
        for commodity, qty, sfrom, sto in TRANSFERS_TABLE.get(month, []):
            movements.append({
                "id": f"M{mov_id:03d}",
                "date": f"{month}-{day:02d}",
                "type": "transfer",
                "commodity": commodity,
                "quantity": qty,
                "unit_price": COMMODITIES[commodity]["unit_price"],
                "site_from": sfrom,
                "site_to": sto,
            })
            mov_id += 1
            day += 3

    # --- Returns ---
    if has_returns:
        for commodity, qty, customer in RETURNS_TABLE.get(month, []):
            movements.append({
                "id": f"M{mov_id:03d}",
                "date": f"{month}-{day:02d}",
                "type": "return",
                "commodity": commodity,
                "quantity": qty,
                "unit_price": COMMODITIES[commodity]["unit_price"],
                "site": "WH1",
                "customer": customer,
            })
            mov_id += 1
            day += 3

    # --- Loss ---
    movements.append({
        "id": f"M{mov_id:03d}",
        "date": f"{month}-28",
        "type": "loss",
        "commodity": loss_commodity,
        "quantity": loss_qty,
        "unit_price": COMMODITIES[loss_commodity]["unit_price"],
        "site": "WH1",
    })

    # --- Stock entries ---
    # Compute closing balances from opening minus sales/transfers/losses plus returns
    balances = dict(DEFAULT_OPENING)  # copy
    for mov in movements:
        c = mov["commodity"]
        q = mov["quantity"]
        if mov["type"] == "sale":
            balances[c] -= q
        elif mov["type"] == "transfer":
            if mov.get("site_from") == "WH1":
                balances[c] -= q
        elif mov["type"] == "return":
            balances[c] += q
        elif mov["type"] == "loss":
            balances[c] -= q

    stock_entries = []
    sid = 1
    for commodity in ["spirits", "tobacco", "beer", "wine"]:
        stock_entries.append({
            "id": f"S{sid:03d}",
            "commodity": commodity,
            "site": "WH1",
            "opening_balance": DEFAULT_OPENING[commodity],
            "closing_balance": balances[commodity],
        })
        sid += 1

    # --- Completed return ---
    duty_lines, total_duty = compute_duty_lines(movements, stock_entries)

    completed_return = {
        "month": month,
        "duty_lines": duty_lines,
        "total_duty": total_duty,
        "confirmation_code": f"CONF-{month}-practice{month.replace('-', '')}",
        "reference": f"REF-{month}-practice{month.replace('-', '')}",
    }

    return movements, stock_entries, completed_return


def generate_portal_examples():
    """Generate static portal example audit logs."""
    examples = {}

    # --- None (clean submit → confirm) ---
    for i in range(1, 4):
        month_label = f"EX-N{i}"
        ref = f"REF-EX-N{i}-a{i}b{i}c{i}"
        conf = f"CONF-EX-N{i}-d{i}e{i}f{i}"
        rid = f"RET-EX-N{i}"
        examples[f"none_{i}"] = [
            {
                "action": "submit",
                "request_id": rid,
                "month": "2024-01",
                "reference": ref,
                "timestamp": f"2024-01-31T10:00:0{i-1}+00:00",
                "status": "200",
                "duplicate": False,
            },
            {
                "action": "confirm",
                "request_id": rid,
                "reference": ref,
                "confirmation_code": conf,
                "timestamp": f"2024-01-31T10:00:0{i}+00:00",
                "status": "200",
                "duplicate": False,
            },
        ]

    # --- One 503 on submit ---
    for i in range(1, 4):
        ref = f"REF-EX-503-{i}-a{i}b{i}"
        conf = f"CONF-EX-503-{i}-c{i}d{i}"
        rid = f"RET-EX-503-{i}"
        examples[f"one_503_{i}"] = [
            {
                "action": "submit",
                "request_id": rid,
                "month": "2024-02",
                "reference": ref,
                "timestamp": f"2024-02-28T10:00:00+00:00",
                "status": "503",
                "fault": True,
            },
            {
                "action": "submit",
                "request_id": rid,
                "month": "2024-02",
                "reference": ref,
                "timestamp": f"2024-02-28T10:00:01+00:00",
                "status": "200",
                "idempotent": True,
                "duplicate": False,
            },
            {
                "action": "confirm",
                "request_id": rid,
                "reference": ref,
                "confirmation_code": conf,
                "timestamp": f"2024-02-28T10:00:02+00:00",
                "status": "200",
                "duplicate": False,
            },
        ]

    # --- 503 then duplicate risk (both submit and confirm fault) ---
    for i in range(1, 4):
        ref = f"REF-EX-DUP-{i}-a{i}b{i}"
        conf = f"CONF-EX-DUP-{i}-c{i}d{i}"
        rid = f"RET-EX-DUP-{i}"
        examples[f"dup_risk_{i}"] = [
            {
                "action": "submit",
                "request_id": rid,
                "month": "2024-03",
                "reference": ref,
                "timestamp": f"2024-03-31T10:00:00+00:00",
                "status": "503",
                "fault": True,
            },
            {
                "action": "submit",
                "request_id": rid,
                "month": "2024-03",
                "reference": ref,
                "timestamp": f"2024-03-31T10:00:01+00:00",
                "status": "200",
                "idempotent": True,
                "duplicate": False,
            },
            {
                "action": "confirm",
                "request_id": rid,
                "reference": ref,
                "confirmation_code": conf,
                "timestamp": f"2024-03-31T10:00:02+00:00",
                "status": "503",
                "fault": True,
                "duplicate": False,
            },
            {
                "action": "confirm",
                "request_id": rid,
                "reference": ref,
                "confirmation_code": conf,
                "timestamp": f"2024-03-31T10:00:03+00:00",
                "status": "200",
                "idempotent": True,
                "duplicate": False,
            },
        ]

    return examples


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(MONTHS_DIR, exist_ok=True)
    os.makedirs(RETURNS_DIR, exist_ok=True)
    os.makedirs(PORTAL_DIR, exist_ok=True)

    # Generate practice months
    for defn in PRACTICE_DEFS:
        month, loss_level, has_transfers, has_returns, loss_comm, loss_open, loss_qty = defn
        movements, stock_entries, completed_return = generate_month(
            month, loss_level, has_transfers, has_returns,
            loss_comm, loss_open, loss_qty,
        )

        # Write movements
        mov_path = os.path.join(MONTHS_DIR, f"movements_{month}.json")
        with open(mov_path, "w") as f:
            json.dump(movements, f, indent=2)

        # Write stock
        stock_path = os.path.join(MONTHS_DIR, f"stock_{month}.json")
        with open(stock_path, "w") as f:
            json.dump(stock_entries, f, indent=2)

        # Write completed return
        ret_path = os.path.join(RETURNS_DIR, f"{month}.json")
        with open(ret_path, "w") as f:
            json.dump(completed_return, f, indent=2)

        print(f"  Generated practice month {month} "
              f"(loss={loss_level}, transfers={has_transfers}, returns={has_returns})")

    # Generate portal examples
    examples = generate_portal_examples()
    for name, audit in examples.items():
        path = os.path.join(PORTAL_DIR, f"{name}.json")
        with open(path, "w") as f:
            json.dump(audit, f, indent=2)
        print(f"  Generated portal example {name}.json")

    print("Practice data generation complete.")


if __name__ == "__main__":
    main()
