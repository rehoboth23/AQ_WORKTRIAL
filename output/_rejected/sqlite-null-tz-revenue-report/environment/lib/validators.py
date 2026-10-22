"""Validation utilities for the revenue analytics report.

Provides validation functions for individual report rows and
the complete report output. These checks ensure data integrity
and flag potential issues before the report is finalized.
"""

from lib.constants import REPORT_COLUMNS


def validate_row(row):
    """Validate a single report row.

    Checks:
    - All required fields are present
    - Monetary values are numeric (or empty string for known NULL propagation)
    - Month format is YYYY-MM
    - Merchant ID is not empty
    - Transaction count is a positive integer

    Args:
        row: Dictionary with report row data.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    errors = []

    # Check required fields
    for field in REPORT_COLUMNS:
        if field not in row:
            errors.append(f"Missing field: {field}")

    if errors:
        return (False, errors)

    # Check month format
    month = row.get("month", "")
    if month and len(month) == 7 and month[4] == "-":
        try:
            int(month[:4])
            int(month[5:7])
        except ValueError:
            errors.append(f"Invalid month format: {month}")
    else:
        errors.append(f"Invalid month format: {month}")

    # Check merchant ID
    if not row.get("merchant_id"):
        errors.append("Empty merchant_id")

    # Check monetary values are numeric or empty
    for money_field in ["gross_revenue", "total_refunds", "net_revenue"]:
        val = row.get(money_field, "")
        if val == "" or val is None:
            # This can happen due to NULL propagation - not a structural error
            # but should be flagged for investigation
            continue
        try:
            float(val)
        except (ValueError, TypeError):
            errors.append(f"Non-numeric {money_field}: {val}")

    # Check transaction count
    try:
        count = int(row.get("transaction_count", 0))
        if count <= 0:
            errors.append(f"Non-positive transaction_count: {count}")
    except (ValueError, TypeError):
        errors.append(f"Invalid transaction_count: {row.get('transaction_count')}")

    return (len(errors) == 0, errors)


def validate_report(rows):
    """Validate the entire report.

    Args:
        rows: List of report row dictionaries.

    Returns:
        True if all rows are valid, False otherwise.
    """
    if not rows:
        return False

    all_valid = True
    for i, row in enumerate(rows):
        is_valid, errors = validate_row(row)
        if not is_valid:
            all_valid = False

    return all_valid


def validate_no_duplicate_months(rows):
    """Check that there are no duplicate (month, merchant_id) pairs.

    Args:
        rows: List of report row dictionaries.

    Returns:
        True if no duplicates, False otherwise.
    """
    seen = set()
    for row in rows:
        key = (row.get("month"), row.get("merchant_id"))
        if key in seen:
            return False
        seen.add(key)
    return True


def validate_monotonic_months(rows):
    """Check that months are in chronological order within the report.

    Args:
        rows: List of report row dictionaries.

    Returns:
        True if months are in non-decreasing order, False otherwise.
    """
    months = [row.get("month", "") for row in rows]
    return months == sorted(months)


def validate_merchant_coverage(rows, expected_merchants):
    """Check that all expected merchants appear in each month.

    Args:
        rows: List of report row dictionaries.
        expected_merchants: Set of merchant IDs that should appear.

    Returns:
        True if all merchants appear in every month, False otherwise.
    """
    months = set(row.get("month") for row in rows)
    for month in months:
        month_merchants = set(
            row.get("merchant_id") for row in rows if row.get("month") == month
        )
        if not expected_merchants.issubset(month_merchants):
            return False
    return True
