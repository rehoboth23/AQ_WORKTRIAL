#!/usr/bin/env python3
"""Public test: basic calculation with round amounts.
Run after starting the Flask app:  python3 webapp.py
Then:  python3 tests_public/test_basic.py
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


def test_valid_application():
    result = post_api("/api/calculate", {
        "applicant_name": "John Smith",
        "loan_amount": "10000",
        "interest_rate": "5",
        "term_months": "12",
        "start_date": "01/01/2025"
    })
    assert result["valid"] is True, f"Expected valid=True, got: {result}"
    assert result["monthly_payment"] == 856.07, \
        f"Expected monthly_payment=856.07, got: {result.get('monthly_payment')}"
    assert len(result["schedule"]) == 12, \
        f"Expected 12 schedule entries, got {len(result.get('schedule', []))}"
    assert result["schedule"][0]["instalment_no"] == 1
    last = result["schedule"][-1]
    assert abs(last["balance"]) < 0.01, \
        f"Last balance should be ~0, got {last['balance']}"
    assert result["total_repayment"] == round(sum(s["payment"] for s in result["schedule"]), 2), \
        "total_repayment should equal sum of payments"
    print("  PASS: valid application calculates correctly")


def test_display_formats():
    result = post_api("/api/calculate", {
        "applicant_name": "John Smith",
        "loan_amount": "10000",
        "interest_rate": "5",
        "term_months": "12",
        "start_date": "01/01/2025"
    })
    disp = result.get("display", {})
    assert "$" in disp.get("monthly_payment", ""), "Currency should have $ sign"
    assert disp.get("interest_rate", "").endswith("%"), "Rate should end with %"
    assert disp.get("start_date") == "01/01/2025", \
        f"Date should be DD/MM/YYYY, got {disp.get('start_date')}"
    print("  PASS: display formats present")


if __name__ == "__main__":
    try:
        urllib.request.urlopen(f"{BASE_URL}/", timeout=2)
    except Exception:
        print("ERROR: Flask app not running on port 5000.")
        print("Start it with:  python3 webapp.py")
        sys.exit(1)

    tests = [test_valid_application, test_display_formats]
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
