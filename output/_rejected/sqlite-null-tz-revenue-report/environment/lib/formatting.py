"""Number formatting utilities for report output.

Provides consistent formatting for monetary values, dates,
and other report fields.
"""


def format_currency(value):
    """Format a numeric value as a currency string with 2 decimal places.

    Args:
        value: A numeric value, None, or empty string.

    Returns:
        Formatted string with 2 decimal places, or empty string for None/empty.
    """
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return ""


def format_month(date_str):
    """Format a date string as YYYY-MM.

    Args:
        date_str: A date string in YYYY-MM-DD or YYYY-MM format.

    Returns:
        String in YYYY-MM format.
    """
    if date_str and len(date_str) >= 7:
        return date_str[:7]
    return date_str


def format_integer(value):
    """Format a numeric value as an integer string.

    Args:
        value: A numeric value.

    Returns:
        Integer string representation.
    """
    if value is None:
        return "0"
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return "0"


def parse_currency(value_str):
    """Parse a currency string back to a float.

    Args:
        value_str: A string representation of a monetary value.

    Returns:
        Float value, or None if parsing fails.
    """
    if not value_str or value_str.strip() == "":
        return None
    try:
        return float(value_str)
    except (ValueError, TypeError):
        return None


def safe_divide(numerator, denominator, default=0.0):
    """Safely divide two values, returning default on zero denominator.

    Args:
        numerator: The numerator value.
        denominator: The denominator value.
        default: Value to return if denominator is zero.

    Returns:
        Division result or default.
    """
    try:
        if float(denominator) == 0:
            return default
        return float(numerator) / float(denominator)
    except (ValueError, TypeError):
        return default
