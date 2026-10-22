#!/usr/bin/env python3
"""Generate journal JSONL files for the tally system.

Creates five daily journal files (2024-01-15 through 2024-01-19) with
financial entries across multiple accounts, including late-arriving
entries, voided entries, and negative-amount accounts.

Run once at build time; the script deletes itself afterwards.
"""

import json
from pathlib import Path

OUT = Path("/app/data/journals")


def w(path: Path, entries: list[dict]) -> None:
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e, separators=(",", ":")) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # ── 2024-01-15 ──────────────────────────────────────────────
    w(OUT / "journal_2024-01-15.jsonl", [
        {"id": "REV-001", "date": "2024-01-15", "account": "Revenue",    "amount": 2500.00, "description": "Product sales"},
        {"id": "REV-002", "date": "2024-01-15", "account": "Revenue",    "amount": 1800.00, "description": "Service revenue"},
        {"id": "SRV-001", "date": "2024-01-15", "account": "Services",   "amount":  950.00, "description": "Consulting engagement"},
        {"id": "REF-001", "date": "2024-01-15", "account": "Refunds",    "amount": -320.00, "description": "Customer refund #1042"},
        {"id": "DIS-001", "date": "2024-01-15", "account": "Discounts",  "amount": -150.00, "description": "Early payment discount"},
        {"id": "PAY-001", "date": "2024-01-15", "account": "Payroll",    "amount": 4200.00, "description": "Weekly payroll"},
        {"id": "RNT-001", "date": "2024-01-15", "account": "Rent",       "amount": 2800.00, "description": "Office lease"},
        {"id": "LTE-001", "date": "2024-01-14", "account": "Revenue",    "amount":  600.00, "description": "Late-arriving sale from 14th"},
        {"id": "LTE-002", "date": "2024-01-14", "account": "Services",   "amount":  300.00, "description": "Late-arriving service from 14th"},
    ])

    # ── 2024-01-16 ──────────────────────────────────────────────
    w(OUT / "journal_2024-01-16.jsonl", [
        {"id": "REV-003", "date": "2024-01-16", "account": "Revenue",    "amount": 3100.00, "description": "Product sales"},
        {"id": "SRV-002", "date": "2024-01-16", "account": "Services",   "amount": 1200.00, "description": "Support contract"},
        {"id": "REF-002", "date": "2024-01-16", "account": "Refunds",    "amount": -450.00, "description": "Customer refund #1043"},
        {"id": "PAY-002", "date": "2024-01-16", "account": "Payroll",    "amount": 4200.00, "description": "Weekly payroll"},
        {"id": "RNT-002", "date": "2024-01-16", "account": "Rent",       "amount": 2800.00, "description": "Office lease"},
        {"id": "CON-001", "date": "2024-01-16", "account": "Consulting", "amount": 3500.00, "description": "Strategy engagement"},
        {"id": "SUP-001", "date": "2024-01-16", "account": "Supplies",   "amount":  480.00, "description": "Office supplies"},
        {"id": "DIS-002", "date": "2024-01-16", "account": "Discounts",  "amount": -200.00, "description": "Volume discount"},
        {"id": "LTE-003", "date": "2024-01-15", "account": "Revenue",    "amount":  750.00, "description": "Late-arriving from 15th"},
    ])

    # ── 2024-01-17 ──────────────────────────────────────────────
    w(OUT / "journal_2024-01-17.jsonl", [
        {"id": "REV-004", "date": "2024-01-17", "account": "Revenue",    "amount": 2800.00, "description": "Product sales"},
        {"id": "SRV-003", "date": "2024-01-17", "account": "Services",   "amount":  850.00, "description": "Training session"},
        {"id": "REF-003", "date": "2024-01-17", "account": "Refunds",    "amount": -280.00, "description": "Customer refund #1044"},
        {"id": "CON-002", "date": "2024-01-17", "account": "Consulting", "amount": 4200.00, "description": "IT assessment"},
        {"id": "PAY-003", "date": "2024-01-17", "account": "Payroll",    "amount": 4200.00, "description": "Weekly payroll"},
        {"id": "SUP-002", "date": "2024-01-17", "account": "Supplies",   "amount":  320.00, "description": "Equipment purchase"},
        {"id": "DIS-003", "date": "2024-01-17", "account": "Discounts",  "amount": -180.00, "description": "Loyalty discount"},
        {"id": "VD-001",  "date": "2024-01-17", "account": "Revenue",    "amount": 1500.00, "description": "Duplicate entry - voided", "voided": True},
        {"id": "LTE-004", "date": "2024-01-16", "account": "Consulting", "amount":  900.00, "description": "Late-arriving from 16th"},
    ])

    # ── 2024-01-18 ──────────────────────────────────────────────
    w(OUT / "journal_2024-01-18.jsonl", [
        {"id": "REV-005", "date": "2024-01-18", "account": "Revenue",    "amount": 3500.00, "description": "Product sales"},
        {"id": "SRV-004", "date": "2024-01-18", "account": "Services",   "amount": 1500.00, "description": "Maintenance contract"},
        {"id": "REF-004", "date": "2024-01-18", "account": "Refunds",    "amount": -380.00, "description": "Customer refund #1045"},
        {"id": "PAY-004", "date": "2024-01-18", "account": "Payroll",    "amount": 4200.00, "description": "Weekly payroll"},
        {"id": "CON-003", "date": "2024-01-18", "account": "Consulting", "amount": 2800.00, "description": "Project milestone"},
        {"id": "SUP-003", "date": "2024-01-18", "account": "Supplies",   "amount":  550.00, "description": "Software licenses"},
        {"id": "RNT-003", "date": "2024-01-18", "account": "Rent",       "amount": 2800.00, "description": "Office lease"},
        {"id": "DIS-004", "date": "2024-01-18", "account": "Discounts",  "amount": -250.00, "description": "Partner discount"},
        {"id": "LTE-005", "date": "2024-01-17", "account": "Revenue",    "amount": 1100.00, "description": "Late-arriving from 17th"},
    ])

    # ── 2024-01-19 ──────────────────────────────────────────────
    w(OUT / "journal_2024-01-19.jsonl", [
        {"id": "REV-006", "date": "2024-01-19", "account": "Revenue",    "amount": 4200.00, "description": "Product sales"},
        {"id": "SRV-005", "date": "2024-01-19", "account": "Services",   "amount": 1800.00, "description": "SLA contract"},
        {"id": "REF-005", "date": "2024-01-19", "account": "Refunds",    "amount": -520.00, "description": "Customer refund #1046"},
        {"id": "CON-004", "date": "2024-01-19", "account": "Consulting", "amount": 3100.00, "description": "Advisory retainer"},
        {"id": "PAY-005", "date": "2024-01-19", "account": "Payroll",    "amount": 4200.00, "description": "Weekly payroll"},
        {"id": "SUP-004", "date": "2024-01-19", "account": "Supplies",   "amount":  380.00, "description": "Office restock"},
        {"id": "DIS-005", "date": "2024-01-19", "account": "Discounts",  "amount": -300.00, "description": "Seasonal promotion"},
        {"id": "RNT-004", "date": "2024-01-19", "account": "Rent",       "amount": 2800.00, "description": "Office lease"},
        {"id": "LTE-006", "date": "2024-01-18", "account": "Services",   "amount":  650.00, "description": "Late-arriving from 18th"},
    ])

    print(f"Generated 5 journal files in {OUT}")


if __name__ == "__main__":
    main()
