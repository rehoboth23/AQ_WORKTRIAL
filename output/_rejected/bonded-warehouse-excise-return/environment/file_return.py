#!/usr/bin/env python3
"""File the excise-duty return for bonded warehouse WH1.

FIXME: This script has several known issues that must be corrected
before it can produce a valid excise-duty return.
"""
import json
import urllib.request

MONTH = "2024-03"


def main():
    # Fetch movements from ERP
    with urllib.request.urlopen(
        f"http://localhost:5001/movements?month={MONTH}"
    ) as resp:
        movements = json.loads(resp.read())

    # Calculate duty for all movements using unit_price
    duty_lines = []
    total_duty = 0.0

    for mov in movements:
        duty = mov["quantity"] * mov["unit_price"]
        duty_lines.append(
            {
                "commodity": mov["commodity"],
                "duty_type": mov["type"],
                "quantity": mov["quantity"],
                "duty": round(duty, 2),
            }
        )
        total_duty += duty

    total_duty = round(total_duty, 2)

    # Submit to portal
    body = json.dumps(
        {
            "month": MONTH,
            "duty_lines": duty_lines,
            "total_duty": total_duty,
        }
    ).encode()

    req = urllib.request.Request(
        "http://localhost:5003/submit",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    print(f"Submitted: reference={result.get('reference')}")


if __name__ == "__main__":
    main()
