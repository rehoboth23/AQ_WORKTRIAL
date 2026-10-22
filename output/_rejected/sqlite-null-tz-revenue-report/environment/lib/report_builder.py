"""Report builder module for the revenue analytics pipeline.

This module queries the database views and applies final transformations
to produce the report data. It reads configuration from the loaded config
and applies the conversion rate to all monetary values.

Business Rules (from Operations Guide):
========================================
1. Currency: All monetary amounts in the transaction ledger are recorded
   in US Dollars (USD). The conversion_rate in config.yaml under
   reporting.currency is used to convert from ledger currency to the
   reporting currency. When the reporting currency is USD and the ledger
   currency is USD, the conversion rate must be 1.0.

2. Transaction Eligibility:
   - Only transactions with status = 'completed' are included
   - Transactions with category = 'internal' are EXCLUDED
   - Transactions with category = 'subscription' are included
   - Transactions with category = 'one_time' are included
   - Transactions without a category value (NULL) are ordinary business
     transactions and MUST be included in revenue

3. Refund Handling:
   - refund_amount column is nullable
   - Where refund_amount is not recorded (NULL), the refund is $0.00
   - Net revenue must always be a numeric value (never blank/NULL/empty)

4. Timezone:
   - The company operates on US Eastern Time (UTC-5)
   - All timestamps in the database are stored in UTC
   - Revenue should be attributed to the business date (Eastern Time)
   - Example: 2024-02-01 00:30 UTC = 2024-01-31 19:30 EST -> January

5. Report Format:
   - Columns: month, merchant_id, gross_revenue, total_refunds,
     net_revenue, transaction_count
   - month format: YYYY-MM
   - All monetary values: numeric, rounded to 2 decimal places
   - transaction_count: integer
"""

from lib.constants import DEFAULT_CONVERSION_RATE, REPORT_COLUMNS


def get_conversion_rate(config):
    """Extract the conversion rate from the configuration.

    Args:
        config: Loaded configuration dictionary.

    Returns:
        The conversion rate as a float. Defaults to 1.0 if not specified.
    """
    rate = (
        config.get("reporting", {})
        .get("currency", {})
        .get("conversion_rate", DEFAULT_CONVERSION_RATE)
    )
    return float(rate)


def apply_conversion(value, rate):
    """Apply the currency conversion rate to a monetary value.

    Args:
        value: The monetary value (float or None).
        rate: The conversion rate.

    Returns:
        The converted value rounded to 2 decimal places,
        or empty string if value is None.
    """
    if value is None:
        return ""
    return round(float(value) * rate, 2)


def build_report(conn, config):
    """Build monthly revenue report from v_monthly_summary view.

    Queries the pre-computed v_monthly_summary view and applies the
    configured conversion rate to all monetary values.

    Args:
        conn: SQLite database connection with row factory set.
        config: Loaded configuration dictionary.

    Returns:
        List of dictionaries, one per (month, merchant_id) combination,
        with keys matching the report column names.
    """
    rate = get_conversion_rate(config)
    currency_code = (
        config.get("reporting", {}).get("currency", {}).get("code", "USD")
    )
    print(f"Building report with conversion rate {rate} (currency: {currency_code})")

    cursor = conn.execute(
        """
        SELECT month, merchant_id, gross_revenue, total_refunds,
               net_revenue, transaction_count
        FROM v_monthly_summary
        ORDER BY month, merchant_id
    """
    )

    rows = []
    for row in cursor:
        gross = apply_conversion(row["gross_revenue"], rate)
        refunds = apply_conversion(row["total_refunds"], rate)
        net = apply_conversion(row["net_revenue"], rate)

        rows.append(
            {
                "month": row["month"],
                "merchant_id": row["merchant_id"],
                "gross_revenue": gross,
                "total_refunds": refunds,
                "net_revenue": net,
                "transaction_count": row["transaction_count"],
            }
        )

    return rows
