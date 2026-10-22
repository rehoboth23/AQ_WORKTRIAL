"""Date utility functions for the revenue analytics pipeline.

Provides helper functions for date manipulation, timezone conversion,
and business date calculation. Note: Some of these utilities are
used by the reporting views directly (via SQLite date functions),
while others are available for Python-level date processing.

The primary timezone conversion for reporting is handled in the SQL
views using SQLite's date modifiers (e.g., date(col, '-5 hours')).
"""

from datetime import datetime, timedelta, timezone

# US Eastern Standard Time offset (no DST handling for simplicity)
EST_OFFSET = timezone(timedelta(hours=-5))
UTC = timezone.utc


def utc_to_est(utc_dt):
    """Convert a UTC datetime to EST.

    Args:
        utc_dt: A timezone-aware datetime in UTC, or a naive datetime
                assumed to be UTC.

    Returns:
        A timezone-aware datetime in EST.
    """
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=UTC)
    return utc_dt.astimezone(EST_OFFSET)


def est_business_date(utc_dt):
    """Get the business date (EST) for a UTC datetime.

    This is the Python equivalent of SQLite's date(created_at, '-5 hours').

    Args:
        utc_dt: A datetime in UTC (naive datetimes are assumed UTC).

    Returns:
        A date object representing the EST business date.
    """
    est_dt = utc_to_est(utc_dt)
    return est_dt.date()


def est_business_month(utc_dt):
    """Get the business month (YYYY-MM) for a UTC datetime.

    Args:
        utc_dt: A datetime in UTC (naive datetimes are assumed UTC).

    Returns:
        A string in YYYY-MM format representing the EST business month.
    """
    est_dt = utc_to_est(utc_dt)
    return est_dt.strftime("%Y-%m")


def parse_utc_timestamp(ts_string):
    """Parse a UTC timestamp string into a datetime object.

    Args:
        ts_string: A string in 'YYYY-MM-DD HH:MM:SS' format.

    Returns:
        A timezone-aware datetime in UTC.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    dt = datetime.strptime(ts_string, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=UTC)


def month_range(start_month, end_month):
    """Generate a range of month strings from start to end (inclusive).

    Args:
        start_month: Start month in YYYY-MM format.
        end_month: End month in YYYY-MM format.

    Yields:
        Month strings in YYYY-MM format.
    """
    year, month = map(int, start_month.split("-"))
    end_year, end_month_num = map(int, end_month.split("-"))

    while (year, month) <= (end_year, end_month_num):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month > 12:
            month = 1
            year += 1


def days_in_month(year, month):
    """Return the number of days in a given month.

    Args:
        year: The year (integer).
        month: The month (1-12).

    Returns:
        Number of days in the month.
    """
    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        return 28
    elif month in [4, 6, 9, 11]:
        return 30
    else:
        return 31


def quarter_for_month(month_str):
    """Return the quarter number for a YYYY-MM string.

    Args:
        month_str: Month string in YYYY-MM format.

    Returns:
        Quarter number (1-4).
    """
    month_num = int(month_str.split("-")[1])
    return (month_num - 1) // 3 + 1


def is_month_boundary_utc(utc_dt, offset_hours=-5):
    """Check if a UTC datetime falls on a month boundary in the target timezone.

    A month boundary occurs when the UTC date and the local date are in
    different months (e.g., 2024-02-01 00:30 UTC is still January in EST).

    Args:
        utc_dt: A datetime in UTC.
        offset_hours: Timezone offset from UTC (negative for west).

    Returns:
        True if the UTC and local dates are in different months.
    """
    offset = timedelta(hours=offset_hours)
    local_dt = utc_dt + offset
    return (utc_dt.year, utc_dt.month) != (local_dt.year, local_dt.month)
