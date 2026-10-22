"""Utility functions for the account service.

General-purpose helper functions used across the service for
formatting, parsing, and common operations.
"""
import re
from datetime import datetime, timezone


def format_currency(amount):
    """Format a balance amount as a currency string.

    Args:
        amount: The numeric balance value.

    Returns:
        A formatted string like '$1,234.56'.
    """
    return f"${amount:,.2f}"


def parse_float(value, default=0.0):
    """Safely parse a float value.

    Args:
        value: The value to parse.
        default: Default value if parsing fails.

    Returns:
        The parsed float, or the default.
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def is_valid_email(email):
    """Basic email format validation.

    Args:
        email: The email address to validate.

    Returns:
        True if the email matches a basic pattern.
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def now_iso():
    """Return current UTC time in ISO 8601 format.

    Returns:
        A string like '2024-01-15T10:30:00+00:00'.
    """
    return datetime.now(timezone.utc).isoformat()


def truncate(s, max_len=50):
    """Truncate a string to max_len, adding ellipsis if needed.

    Args:
        s: The string to truncate.
        max_len: Maximum length including the ellipsis.

    Returns:
        The truncated string.
    """
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + '...'


def safe_str(value, default=''):
    """Convert a value to string safely.

    Args:
        value: The value to convert.
        default: Default if conversion fails.

    Returns:
        The string representation.
    """
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def parse_iso_datetime(s):
    """Parse an ISO 8601 datetime string.

    Args:
        s: The datetime string to parse.

    Returns:
        A datetime object, or None if parsing fails.
    """
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def calculate_percentage(part, total):
    """Calculate what percentage part is of total.

    Args:
        part: The numerator.
        total: The denominator.

    Returns:
        The percentage as a float, or 0.0 if total is 0.
    """
    if total == 0:
        return 0.0
    return (part / total) * 100.0


def slugify(text, separator='_'):
    """Convert text to a URL/filename-safe slug.

    Args:
        text: The text to slugify.
        separator: The separator character.

    Returns:
        A lowercase string with non-alphanumeric chars replaced.
    """
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s-]+', separator, text)
    return text.strip(separator)
