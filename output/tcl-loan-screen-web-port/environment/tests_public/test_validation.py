#!/usr/bin/env python3
"""Public test: basic single-field validation error.
Run after starting the Flask app:  python3 webapp.py
Then:  python3 tests_public/test_validation.py
"""
import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:5000"


def post_api(endpoint, data):
    url = f"{BASE_URL}{endpoint}"
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=encoded, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def test_empty_name():
    result = post_api("/api/calculate", {
        "applicant_name": "",
        "loan_amount": "10000",
        "interest_rate": "5",
        "term_months": "12",
        "start_date": "01/01/2025"
    })
    assert result["valid"] is False, f"Expected valid=False, got: {result}"
    assert result.get("error") == "Applicant name is required.", \
        f"Expected 'Applicant name is required.', got: {result.get('error')}"
    print("  PASS: empty name returns correct error")


def test_name_too_short():
    result = post_api("/api/calculate", {
        "applicant_name": "A",
        "loan_amount": "10000",
        "interest_rate": "5",
        "term_months": "12",
        "start_date": "01/01/2025"
    })
    assert result["valid"] is False
    assert result.get("error") == "Applicant name must be at least 2 characters.", \
        f"Got: {result.get('error')}"
    print("  PASS: short name returns correct error")


if __name__ == "__main__":
    try:
        urllib.request.urlopen(f"{BASE_URL}/", timeout=2)
    except Exception:
        print("ERROR: Flask app not running on port 5000.")
        print("Start it with:  python3 webapp.py")
        sys.exit(1)

    tests = [test_empty_name, test_name_too_short]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
