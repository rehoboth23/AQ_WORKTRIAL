#!/usr/bin/env python3
"""Generate practice transcript JSON files.
Run at build time; the Dockerfile deletes this script afterwards.
"""
import json
import os
import calendar

TRANSCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcripts')


# ---------------------------------------------------------------------------
# Python replication of the Tcl logic (must match loanapp.tcl exactly)
# ---------------------------------------------------------------------------

def fmt2(value):
    """Round to 2 decimals using C snprintf, matching Tcl format("%.2f", x)."""
    return float("%.2f" % value)


def last_day_of_month(month, year):
    return calendar.monthrange(year, month)[1]


def add_months(date_str, n):
    day = int(date_str[0:2])
    month = int(date_str[3:5])
    year = int(date_str[6:10])
    new_month = month + n
    new_year = year
    while new_month > 12:
        new_month -= 12
        new_year += 1
    while new_month < 1:
        new_month += 12
        new_year -= 1
    last = last_day_of_month(new_month, new_year)
    if day > last:
        day = last
    return f"{day:02d}/{new_month:02d}/{new_year:04d}"


def format_currency(amount):
    return "${:,.2f}".format(amount)


def format_rate(rate):
    return "{:.2f}%".format(rate)


def validate(name, amount, rate, term, start_date):
    if name == "":
        return "Applicant name is required."
    if len(name) < 2:
        return "Applicant name must be at least 2 characters."
    if not re_match(r"^[A-Za-z][A-Za-z \-']*$", name):
        return "Applicant name contains invalid characters."
    if amount == "":
        return "Loan amount is required."
    if not is_double(amount):
        return "Loan amount must be a positive number."
    amt = float(amount)
    if amt <= 0:
        return "Loan amount must be a positive number."
    if amt < 500:
        return "Loan amount must be at least $500."
    if amt > 500000:
        return "Loan amount must not exceed $500,000."
    if rate == "":
        return "Interest rate is required."
    if not is_double(rate):
        return "Interest rate must be a number between 0 and 30."
    rt = float(rate)
    if rt <= 0 or rt >= 30:
        return "Interest rate must be a number between 0 and 30."
    if term == "":
        return "Loan term is required."
    if not re_match(r"^[0-9]+$", term):
        return "Loan term must be a whole number of months."
    tm = int(term)
    if tm < 6 or tm > 360:
        return "Loan term must be between 6 and 360 months."
    if start_date == "":
        return "Start date is required."
    if not re_match(r"^[0-9]{2}/[0-9]{2}/[0-9]{4}$", start_date):
        return "Start date must be in DD/MM/YYYY format."
    day = int(start_date[0:2])
    month = int(start_date[3:5])
    year = int(start_date[6:10])
    if month < 1 or month > 12:
        return "Start date must be in DD/MM/YYYY format."
    last = last_day_of_month(month, year)
    if day < 1 or day > last:
        return "Start date must be in DD/MM/YYYY format."
    if year < 2025:
        return "Start date must be on or after 01/01/2025."
    return ""


def re_match(pattern, string):
    import re
    return bool(re.match(pattern, string))


def is_double(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def calculate_repayment(amount, rate, term, start_date):
    principal = float(amount)
    annual_rate = float(rate)
    monthly_rate = annual_rate / 100.0 / 12.0

    monthly_payment = fmt2(principal * monthly_rate / (1 - (1 + monthly_rate) ** (-term)))

    balance = principal
    schedule = []
    total_payment = 0.0
    total_interest = 0.0

    for i in range(1, term + 1):
        interest = fmt2(balance * monthly_rate)
        if i == term:
            principal_part = balance
            payment = fmt2(principal_part + interest)
        else:
            principal_part = fmt2(monthly_payment - interest)
            payment = monthly_payment
        balance = fmt2(balance - principal_part)
        payment_date = add_months(start_date, i)
        schedule.append({
            'instalment_no': i,
            'payment_date': payment_date,
            'payment': payment,
            'principal': principal_part,
            'interest': interest,
            'balance': balance
        })
        total_payment += payment
        total_interest += interest

    return {
        'monthly_payment': monthly_payment,
        'total_repayment': fmt2(total_payment),
        'total_interest': fmt2(total_interest),
        'schedule': schedule
    }


def compute_db_format(amount, rate, start_date):
    return {
        'loan_amount_cents': int(round(float(amount) * 100)),
        'interest_rate_bps': int(round(float(rate) * 100)),
        'start_date': start_date
    }


# ---------------------------------------------------------------------------
# Scenario definitions — 28 transcripts covering every quirk-dimension level
# at least 3 times.
# ---------------------------------------------------------------------------

SCENARIOS = [
    # 1-5: one_field × round × save
    {"id": 1, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save"},
     "desc": "Valid app $10,000 at 5% for 12 months",
     "input": {"applicant_name": "John Smith", "loan_amount": "10000", "interest_rate": "5",
               "term_months": "12", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 2, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save"},
     "desc": "Valid app $25,000 at 7.5% for 24 months",
     "input": {"applicant_name": "Mary Johnson", "loan_amount": "25000", "interest_rate": "7.5",
               "term_months": "24", "start_date": "01/03/2025"}, "action": "calculate"},

    {"id": 3, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save"},
     "desc": "Valid app $50,000 at 3.25% for 60 months",
     "input": {"applicant_name": "Robert Brown", "loan_amount": "50000", "interest_rate": "3.25",
               "term_months": "60", "start_date": "15/06/2025"}, "action": "calculate"},

    {"id": 4, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save"},
     "desc": "Valid app $5,000 at 10% for 6 months",
     "input": {"applicant_name": "Jane Doe", "loan_amount": "5000", "interest_rate": "10",
               "term_months": "6", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 5, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save"},
     "desc": "Valid app $100,000 at 4.25% for 120 months",
     "input": {"applicant_name": "William Davis", "loan_amount": "100000", "interest_rate": "4.25",
               "term_months": "120", "start_date": "01/09/2025"}, "action": "calculate"},

    # 6-8: two_fields × round × save
    {"id": 6, "tags": {"errors_at_once": "two_fields", "amounts": "round", "actions": "save"},
     "desc": "Empty name + amount below minimum",
     "input": {"applicant_name": "", "loan_amount": "100", "interest_rate": "5",
               "term_months": "12", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 7, "tags": {"errors_at_once": "two_fields", "amounts": "round", "actions": "save"},
     "desc": "Name too short/invalid + rate at boundary 30",
     "input": {"applicant_name": "1", "loan_amount": "10000", "interest_rate": "30",
               "term_months": "12", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 8, "tags": {"errors_at_once": "two_fields", "amounts": "round", "actions": "save"},
     "desc": "Amount zero + term below minimum",
     "input": {"applicant_name": "Alice Green", "loan_amount": "0", "interest_rate": "5",
               "term_months": "3", "start_date": "01/01/2025"}, "action": "calculate"},

    # 9-11: three_with_precedence × round × save
    {"id": 9, "tags": {"errors_at_once": "three_with_precedence", "amounts": "round", "actions": "save"},
     "desc": "Empty name + low amount + rate at boundary",
     "input": {"applicant_name": "", "loan_amount": "100", "interest_rate": "30",
               "term_months": "12", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 10, "tags": {"errors_at_once": "three_with_precedence", "amounts": "round", "actions": "save"},
     "desc": "Name invalid chars + amount zero + rate at boundary",
     "input": {"applicant_name": "A1", "loan_amount": "0", "interest_rate": "30",
               "term_months": "12", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 11, "tags": {"errors_at_once": "three_with_precedence", "amounts": "round", "actions": "save"},
     "desc": "Name too short + amount zero + rate boundary + term too short",
     "input": {"applicant_name": "1", "loan_amount": "0", "interest_rate": "30",
               "term_months": "3", "start_date": "01/01/2025"}, "action": "calculate"},

    # 12-14: one_field × round × save_then_edit
    {"id": 12, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save_then_edit"},
     "desc": "Save $10,000 then edit amount to $15,000",
     "input": {"applicant_name": "John Smith", "loan_amount": "10000", "interest_rate": "5",
               "term_months": "12", "start_date": "01/01/2025"},
     "edit_input": {"applicant_name": "John Smith", "loan_amount": "15000", "interest_rate": "5",
                    "term_months": "12", "start_date": "01/01/2025"}, "action": "save_then_edit"},

    {"id": 13, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save_then_edit"},
     "desc": "Save $10,000 then edit rate to 7.5%",
     "input": {"applicant_name": "Mary Johnson", "loan_amount": "10000", "interest_rate": "5",
               "term_months": "12", "start_date": "01/01/2025"},
     "edit_input": {"applicant_name": "Mary Johnson", "loan_amount": "10000", "interest_rate": "7.5",
                    "term_months": "12", "start_date": "01/01/2025"}, "action": "save_then_edit"},

    {"id": 14, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "save_then_edit"},
     "desc": "Save $10,000 then edit term to 24 months",
     "input": {"applicant_name": "Robert Brown", "loan_amount": "10000", "interest_rate": "5",
               "term_months": "12", "start_date": "01/01/2025"},
     "edit_input": {"applicant_name": "Robert Brown", "loan_amount": "10000", "interest_rate": "5",
                    "term_months": "24", "start_date": "01/01/2025"}, "action": "save_then_edit"},

    # 15-17: one_field × cents × save
    {"id": 15, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "save"},
     "desc": "Valid app $15,333.50 at 4.75% for 24 months",
     "input": {"applicant_name": "Sarah O'Brien", "loan_amount": "15333.50", "interest_rate": "4.75",
               "term_months": "24", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 16, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "save"},
     "desc": "Valid app $7,250.25 at 6.5% for 18 months",
     "input": {"applicant_name": "Thomas Lee", "loan_amount": "7250.25", "interest_rate": "6.5",
               "term_months": "18", "start_date": "15/02/2025"}, "action": "calculate"},

    {"id": 17, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "save"},
     "desc": "Valid app $3,999.99 at 8.25% for 12 months",
     "input": {"applicant_name": "Emily White", "loan_amount": "3999.99", "interest_rate": "8.25",
               "term_months": "12", "start_date": "01/04/2025"}, "action": "calculate"},

    # 18-20: one_field × rounding_boundary × save
    {"id": 18, "tags": {"errors_at_once": "one_field", "amounts": "rounding_boundary", "actions": "save"},
     "desc": "Valid app $12,345 at 3.75% for 36 months",
     "input": {"applicant_name": "David Wilson", "loan_amount": "12345", "interest_rate": "3.75",
               "term_months": "36", "start_date": "01/01/2025"}, "action": "calculate"},

    {"id": 19, "tags": {"errors_at_once": "one_field", "amounts": "rounding_boundary", "actions": "save"},
     "desc": "Valid app $9,876.50 at 5.5% for 48 months",
     "input": {"applicant_name": "Patricia King", "loan_amount": "9876.50", "interest_rate": "5.5",
               "term_months": "48", "start_date": "01/03/2025"}, "action": "calculate"},

    {"id": 20, "tags": {"errors_at_once": "one_field", "amounts": "rounding_boundary", "actions": "save"},
     "desc": "Valid app $25,000 at 4.5% for 30 months",
     "input": {"applicant_name": "Michael Scott", "loan_amount": "25000", "interest_rate": "4.5",
               "term_months": "30", "start_date": "01/06/2025"}, "action": "calculate"},

    # 21-23: one_field × round × delete_with_dependents
    {"id": 21, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "delete_with_dependents"},
     "desc": "Save $10,000 app then delete with schedule entries",
     "input": {"applicant_name": "John Smith", "loan_amount": "10000", "interest_rate": "5",
               "term_months": "12", "start_date": "01/01/2025"}, "action": "save_then_delete"},

    {"id": 22, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "delete_with_dependents"},
     "desc": "Save $25,000 app then delete with schedule entries",
     "input": {"applicant_name": "Mary Johnson", "loan_amount": "25000", "interest_rate": "7.5",
               "term_months": "24", "start_date": "01/03/2025"}, "action": "save_then_delete"},

    {"id": 23, "tags": {"errors_at_once": "one_field", "amounts": "round", "actions": "delete_with_dependents"},
     "desc": "Save $5,000 app then delete with schedule entries",
     "input": {"applicant_name": "Jane Doe", "loan_amount": "5000", "interest_rate": "10",
               "term_months": "6", "start_date": "01/01/2025"}, "action": "save_then_delete"},

    # 24-26: one_field × cents × save_then_edit
    {"id": 24, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "save_then_edit"},
     "desc": "Save $15,333.50 then edit amount to $20,000",
     "input": {"applicant_name": "Sarah O'Brien", "loan_amount": "15333.50", "interest_rate": "4.75",
               "term_months": "24", "start_date": "01/01/2025"},
     "edit_input": {"applicant_name": "Sarah O'Brien", "loan_amount": "20000", "interest_rate": "4.75",
                    "term_months": "24", "start_date": "01/01/2025"}, "action": "save_then_edit"},

    {"id": 25, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "save_then_edit"},
     "desc": "Save $7,250.25 then edit rate to 6%",
     "input": {"applicant_name": "Thomas Lee", "loan_amount": "7250.25", "interest_rate": "6.5",
               "term_months": "18", "start_date": "15/02/2025"},
     "edit_input": {"applicant_name": "Thomas Lee", "loan_amount": "7250.25", "interest_rate": "6",
                    "term_months": "18", "start_date": "15/02/2025"}, "action": "save_then_edit"},

    {"id": 26, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "save_then_edit"},
     "desc": "Save $3,999.99 then edit term to 24 months",
     "input": {"applicant_name": "Emily White", "loan_amount": "3999.99", "interest_rate": "8.25",
               "term_months": "12", "start_date": "01/04/2025"},
     "edit_input": {"applicant_name": "Emily White", "loan_amount": "3999.99", "interest_rate": "8.25",
                    "term_months": "24", "start_date": "01/04/2025"}, "action": "save_then_edit"},

    # 27-28: delete_with_dependents with cents/boundary amounts
    {"id": 27, "tags": {"errors_at_once": "one_field", "amounts": "cents", "actions": "delete_with_dependents"},
     "desc": "Save $15,333.50 app then delete with schedule entries",
     "input": {"applicant_name": "Sarah O'Brien", "loan_amount": "15333.50", "interest_rate": "4.75",
               "term_months": "24", "start_date": "01/01/2025"}, "action": "save_then_delete"},

    {"id": 28, "tags": {"errors_at_once": "one_field", "amounts": "rounding_boundary", "actions": "delete_with_dependents"},
     "desc": "Save $12,345 app then delete with schedule entries",
     "input": {"applicant_name": "David Wilson", "loan_amount": "12345", "interest_rate": "3.75",
               "term_months": "36", "start_date": "01/01/2025"}, "action": "save_then_delete"},
]


def build_expected(inp):
    """Compute expected output for a given input dict."""
    err = validate(
        inp.get('applicant_name', ''),
        inp.get('loan_amount', ''),
        inp.get('interest_rate', ''),
        inp.get('term_months', ''),
        inp.get('start_date', '')
    )
    if err:
        return {"valid": False, "error": err}
    calc = calculate_repayment(
        inp['loan_amount'], inp['interest_rate'],
        int(inp['term_months']), inp['start_date']
    )
    rate = float(inp['interest_rate'])
    calc['display'] = {
        'monthly_payment': format_currency(calc['monthly_payment']),
        'total_repayment': format_currency(calc['total_repayment']),
        'total_interest': format_currency(calc['total_interest']),
        'interest_rate': format_rate(rate),
        'start_date': inp['start_date']
    }
    calc['database_format'] = compute_db_format(
        inp['loan_amount'], inp['interest_rate'], inp['start_date']
    )
    calc['valid'] = True
    return calc


def generate():
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    for sc in SCENARIOS:
        sid = sc['id']
        inp = sc['input']
        expected = build_expected(inp)
        record = {
            "scenario": f"scenario_{sid:02d}",
            "tags": sc['tags'],
            "description": sc['desc'],
            "input": inp,
            "action": sc['action'],
            "expected": expected
        }
        if sc['action'] == 'save_then_edit':
            edit_inp = sc['edit_input']
            edit_expected = build_expected(edit_inp)
            record['edit_input'] = edit_inp
            record['edit_expected'] = edit_expected
        if sc['action'] == 'save_then_delete':
            record['delete_confirmation'] = "Confirm deletion of application #1?"
            record['delete_confirmed'] = "Application #1 deleted."
            record['database_after_delete'] = {
                "applications_count": 0,
                "schedule_entries_count": 0
            }
        path = os.path.join(TRANSCRIPTS_DIR, f"scenario_{sid:02d}.json")
        with open(path, 'w') as f:
            json.dump(record, f, indent=2)
        print(f"  wrote {path}")
    print(f"Generated {len(SCENARIOS)} transcripts in {TRANSCRIPTS_DIR}")


if __name__ == '__main__':
    generate()
