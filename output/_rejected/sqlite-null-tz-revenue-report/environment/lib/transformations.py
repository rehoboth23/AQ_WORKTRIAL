"""Data transformation utilities.

NOTE: These utilities are available but not currently used by the
report generation pipeline. They were developed for a planned
ETL overhaul that has not been completed. The SQL views handle
date transformations directly using SQLite date functions.
"""

from datetime import datetime, timedelta, timezone


# US Eastern Standard Time offset (no DST handling for simplicity)
EST_OFFSET = timezone(timedelta(hours=-5))
UTC_TZ = timezone.utc


class DateTransformer:
    """Transform UTC dates to local business dates."""

    def __init__(self, utc_offset_hours=-5):
        """Initialize with a UTC offset.

        Args:
            utc_offset_hours: Hours offset from UTC (negative for west).
                              Default is -5 for US Eastern Standard Time.
        """
        self.offset = timedelta(hours=utc_offset_hours)
        self.tz = timezone(self.offset)

    def utc_to_local(self, utc_dt):
        """Convert UTC datetime to local business datetime.

        Args:
            utc_dt: A timezone-aware datetime in UTC, or a naive datetime
                    assumed to be UTC.

        Returns:
            A timezone-aware datetime in the local timezone.
        """
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=UTC_TZ)
        return utc_dt.astimezone(self.tz)

    def get_business_date(self, utc_dt):
        """Get the business date (local timezone) for a UTC datetime.

        This is the Python equivalent of SQLite's
        date(created_at, '-5 hours').

        Args:
            utc_dt: A datetime in UTC (naive datetimes are assumed UTC).

        Returns:
            A date object representing the local business date.
        """
        local_dt = self.utc_to_local(utc_dt)
        return local_dt.date()

    def get_business_month(self, utc_dt):
        """Get the business month (YYYY-MM) for a UTC datetime.

        Args:
            utc_dt: A datetime in UTC (naive datetimes are assumed UTC).

        Returns:
            A string in YYYY-MM format representing the business month.
        """
        local_dt = self.utc_to_local(utc_dt)
        return local_dt.strftime("%Y-%m")

    def format_for_sqlite(self, utc_dt):
        """Format a UTC datetime for use in SQLite date() modifiers.

        Args:
            utc_dt: A datetime in UTC.

        Returns:
            String like '-5 hours' suitable for SQLite date() modifier.
        """
        hours = int(self.offset.total_seconds() / 3600)
        return f"{hours} hours"


class AmountTransformer:
    """Transform monetary amounts with currency conversion."""

    def __init__(self, conversion_rate=1.0):
        """Initialize with a conversion rate.

        Args:
            conversion_rate: Rate to multiply amounts by.
        """
        self.rate = conversion_rate

    def convert(self, amount):
        """Apply conversion rate to an amount.

        Args:
            amount: The monetary amount.

        Returns:
            Converted amount rounded to 2 decimal places.
        """
        if amount is None:
            return 0.0
        return round(float(amount) * self.rate, 2)

    def net_revenue(self, gross, refunds):
        """Calculate net revenue from gross and refunds.

        Args:
            gross: Gross revenue amount.
            refunds: Total refund amount (None treated as 0).

        Returns:
            Net revenue = gross - refunds.
        """
        if refunds is None:
            refunds = 0.0
        return round(float(gross) - float(refunds), 2)
