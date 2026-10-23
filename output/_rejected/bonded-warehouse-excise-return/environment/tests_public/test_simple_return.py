#!/usr/bin/env python3
"""Public test: file a simple return with two commodities, no special movements, no faults.

This test covers about 30% of the hidden checks: basic sales duty calculation
with the correct commodity rate and two-step submission. It does not include
any boundary case, transfer, return, loss, portal fault, or unit_price trap.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

DATA_DIR = "/app/data"
MONTH = "2024-03"


def _save_and_swap(movements, stock, portal_config):
    """Back up original data files and write test data."""
    backups = {}
    for name, data in [
        (f"movements_{MONTH}.json", movements),
        (f"stock_{MONTH}.json", stock),
        ("portal_config.json", portal_config),
    ]:
        path = os.path.join(DATA_DIR, name)
        with open(path) as f:
            backups[name] = f.read()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    return backups


def _restore(backups):
    """Restore original data files."""
    for name, content in backups.items():
        path = os.path.join(DATA_DIR, name)
        with open(path, "w") as f:
            f.write(content)


def test_simple_return():
    # Simple test data: sales of two commodities only
    simple_movements = [
        {
            "id": "TM001",
            "date": "2024-03-05",
            "type": "sale",
            "commodity": "spirits",
            "quantity": 50,
            "unit_price": 12.50,
            "site": "WH1",
            "customer": "Test Corp",
        },
        {
            "id": "TM002",
            "date": "2024-03-10",
            "type": "sale",
            "commodity": "beer",
            "quantity": 100,
            "unit_price": 3.00,
            "site": "WH1",
            "customer": "Test Corp",
        },
    ]
    simple_stock = [
        {
            "id": "TS001",
            "commodity": "spirits",
            "site": "WH1",
            "opening_balance": 1000,
            "closing_balance": 950,
        },
        {
            "id": "TS002",
            "commodity": "beer",
            "site": "WH1",
            "opening_balance": 2000,
            "closing_balance": 1900,
        },
    ]
    simple_config = {"submit_faults": [], "confirm_faults": []}

    backups = _save_and_swap(simple_movements, simple_stock, simple_config)

    try:
        # Start services
        subprocess.run(["bash", "/app/start_services.sh"], check=True, timeout=30)
        time.sleep(1)

        # Reset portal state
        try:
            req = urllib.request.Request(
                "http://localhost:5003/reset", method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

        # Run the filing script
        result = subprocess.run(
            ["python3", "/app/file_return.py"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PATH": "/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        assert result.returncode == 0, (
            f"Script failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # Check portal has one confirmed submission
        with urllib.request.urlopen(
            "http://localhost:5003/submissions", timeout=5
        ) as resp:
            submissions = json.loads(resp.read())

        confirmed = [s for s in submissions if s.get("confirmed")]
        assert len(confirmed) == 1, (
            f"Expected 1 confirmed submission, got {len(confirmed)}"
        )

        sub = confirmed[0]

        # Expected duty: spirits 50×25=1250, beer 100×5=500, total=1750
        expected_total = 1750.00
        assert abs(sub["total_duty"] - expected_total) < 0.01, (
            f"Expected total duty {expected_total}, got {sub['total_duty']}"
        )

        # Check confirmation file exists
        conf_path = f"/app/returns/{MONTH}/confirmation.json"
        assert os.path.exists(conf_path), "Confirmation file not found"
        with open(conf_path) as f:
            conf = json.load(f)
        assert "confirmation_code" in conf, "confirmation_code missing from archive"
        assert conf.get("month") == MONTH, f"Wrong month in confirmation: {conf.get('month')}"

        print("Simple return test PASSED")

    finally:
        _restore(backups)
        # Clean up confirmation file
        conf_path = f"/app/returns/{MONTH}/confirmation.json"
        if os.path.exists(conf_path):
            os.remove(conf_path)


if __name__ == "__main__":
    test_simple_return()
