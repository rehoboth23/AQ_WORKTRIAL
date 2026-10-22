#!/usr/bin/env python3
"""Generate sample data files for ReportForge.

Creates the CSV transaction log, product catalog, exchange-rate table,
and base formatting configuration.  Run once during image build; the
script itself is deleted afterwards.
"""

import csv
import json
import os
import random
from datetime import date, timedelta

import yaml

random.seed(42)

BASE = "/app"


# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def generate_products():
    """Return the product catalog as a dict."""
    return {
        "P001": {"name": "Widget Alpha"},
        "P002": {"name": "Gadget Beta"},
        "P003": {"name": "Sensor Gamma"},
        "P004": {"name": "Motor Delta"},
        "P005": {"name": "Board Epsilon"},
        "P006": {"name": "Chip Zeta"},
        "P007": {"name": "Cable Eta"},
        "P008": {"name": "Panel Theta"},
        "P009": {"name": "Valve Iota"},
        "P010": {"name": "Bulb Kappa"},
        "P011": {"name": "Filter Lambda"},
        "P012": {"name": "Coil Mu"},
    }


def generate_rates():
    """Return the exchange-rate table as a dict."""
    return {
        "US": {"to_usd": 1.00, "name": "US Dollar"},
        "EU": {"to_usd": 1.10, "name": "Euro"},
        "UK": {"to_usd": 1.27, "name": "British Pound"},
        "JP": {"to_usd": 0.0067, "name": "Japanese Yen"},
        "CA": {"to_usd": 0.74, "name": "Canadian Dollar"},
    }


def generate_transactions(products, rates, n=60):
    """Generate *n* random transaction rows."""
    product_ids = list(products.keys())
    currency_codes = list(rates.keys())

    transactions = []
    start = date(2024, 1, 1)

    for _ in range(n):
        d = start + timedelta(days=random.randint(0, 180))
        pid = random.choice(product_ids)
        qty = random.randint(1, 100)
        price = round(random.uniform(5.0, 500.0), 2)
        curr = random.choice(currency_codes)
        transactions.append({
            "date": d.isoformat(),
            "product_id": pid,
            "quantity": qty,
            "unit_price": f"{price:.2f}",
            "currency": curr,
        })

    transactions.sort(key=lambda t: t["date"])
    return transactions


# ---------------------------------------------------------------------------
# Write files
# ---------------------------------------------------------------------------

def main():
    os.makedirs(f"{BASE}/data", exist_ok=True)
    os.makedirs(f"{BASE}/refdata", exist_ok=True)
    os.makedirs(f"{BASE}/config", exist_ok=True)
    os.makedirs(f"{BASE}/cache", exist_ok=True)

    products = generate_products()
    rates = generate_rates()
    transactions = generate_transactions(products, rates)

    with open(f"{BASE}/refdata/products.json", "w") as f:
        json.dump(products, f, indent=2)

    with open(f"{BASE}/refdata/rates.json", "w") as f:
        json.dump(rates, f, indent=2)

    with open(f"{BASE}/data/transactions.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "product_id", "quantity", "unit_price", "currency"],
        )
        writer.writeheader()
        writer.writerows(transactions)

    formatting = {
        "currency_symbol": "$",
        "decimal_places": 2,
        "date_format": "%Y-%m-%d",
        "heading": "Sales Report",
    }
    with open(f"{BASE}/config/formatting.yml", "w") as f:
        yaml.dump(formatting, f, default_flow_style=False)

    print("ReportForge sample data generated.")


if __name__ == "__main__":
    main()
