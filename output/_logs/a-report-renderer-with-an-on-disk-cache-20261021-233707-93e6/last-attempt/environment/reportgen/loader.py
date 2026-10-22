"""Data loading utilities for ReportForge.

Each ``load_*`` function registers its input file as a cache dependency
via :func:`register_dep`, so the caching layer knows which files to
track for invalidation.
"""

import csv
import json
import os

import yaml


# ---------------------------------------------------------------------------
# Dependency registry
# ---------------------------------------------------------------------------

# Accumulates file paths that influence report output.  Queried by the
# cache layer at lookup and store time.
_registered_deps: list[str] = []


def register_dep(path):
    """Add *path* to the dependency registry (deduplicated)."""
    abs_path = os.path.abspath(path)
    if abs_path not in _registered_deps:
        _registered_deps.append(abs_path)


def get_dependency_paths():
    """Return a snapshot of all registered dependency paths."""
    return list(_registered_deps)


def reset_deps():
    """Clear the dependency registry (called once per invocation)."""
    global _registered_deps
    _registered_deps = []


# ---------------------------------------------------------------------------
# Load functions
# ---------------------------------------------------------------------------

def load_template(report_type):
    """Load the HTML template for *report_type*."""
    template_path = f"/app/templates/{report_type}.html"
    register_dep(template_path)
    with open(template_path) as f:
        return f.read()


def load_formatting():
    """Load base formatting settings from the YAML config."""
    config_path = "/app/config/formatting.yml"
    register_dep(config_path)
    with open(config_path) as f:
        data = yaml.safe_load(f)
        return data if data else {}


def load_overrides():
    """Load optional formatting overrides.

    The overrides file (``/app/config/overrides.yml``) is not required to
    exist.  When absent, no overrides are applied.
    """
    overrides_path = "/app/config/overrides.yml"
    register_dep(overrides_path)
    if not os.path.exists(overrides_path):
        return {}
    with open(overrides_path) as f:
        data = yaml.safe_load(f)
        return data if data else {}


def load_data(csv_path, from_date, to_date):
    """Load CSV transaction rows filtered by date range.

    Dates are compared as strings (ISO YYYY-MM-DD), which is correct for
    the format used in the data files.
    """
    register_dep(csv_path)
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_date = row.get("date", "")
            if from_date <= row_date <= to_date:
                rows.append(row)
    return rows


def load_products():
    """Load the product catalog from the reference data directory."""
    products_path = "/app/refdata/products.json"
    register_dep(products_path)
    with open(products_path) as f:
        return json.load(f)


def load_rates():
    """Load the exchange-rate table from the reference data directory."""
    rates_path = "/app/refdata/rates.json"
    register_dep(rates_path)
    with open(rates_path) as f:
        return json.load(f)
