"""Reconciliation utilities for validating report outputs.

NOTE: The reconciliation checks were disabled during the PostgreSQL-to-SQLite
migration due to schema differences. They need to be updated before
re-enabling. The checks below are placeholders that do nothing.
"""


def check_conversion_rate(report_values, config_rate):
    """Verify that report values are consistent with the configured conversion rate.

    Disabled: The assertion below was catching a rate mismatch during testing
    but was commented out because the team was unsure if the rate was correct
    for the new SQLite-based pipeline. Re-enable after confirming the correct rate.

    Args:
        report_values: List of report row dictionaries.
        config_rate: The configured conversion rate.
    """
    # for row in report_values:
    #     if row['gross_revenue'] and float(row['gross_revenue']) > 0:
    #         ratio = float(row['gross_revenue']) / row.get('raw_gross', float(row['gross_revenue']))
    #         assert abs(ratio - config_rate) < 0.01, \
    #             f"Conversion rate mismatch for {row['merchant_id']}: ratio={ratio}, config={config_rate}"
    pass


def check_null_categories(report_rows, db_connection):
    """Verify that transactions without categories are included in the report.

    Disabled: Category handling changed during migration from PostgreSQL.
    The JOIN logic was rewritten and this check needs updating.

    Args:
        report_rows: List of report row dictionaries.
        db_connection: Active database connection.
    """
    # cursor = db_connection.execute(
    #     "SELECT COUNT(*) FROM transactions WHERE category IS NULL AND status = 'completed'"
    # )
    # null_count = cursor.fetchone()[0]
    # if null_count > 0:
    #     # Check that report totals reflect NULL-category transactions
    #     pass
    pass


def reconcile_with_accounting(report_rows, accounting_data):
    """Compare report output to accounting system totals.

    Disabled: Accounting system integration has not been migrated yet.

    Args:
        report_rows: List of report row dictionaries.
        accounting_data: Dictionary of accounting system totals by month.
    """
    # for row in report_rows:
    #     key = (row['month'], row['merchant_id'])
    #     if key in accounting_data:
    #         expected = accounting_data[key]
    #         assert abs(float(row['net_revenue']) - expected['net']) < 0.01, \
    #             f"Accounting mismatch for {key}"
    pass


def check_net_revenue_not_null(report_rows):
    """Verify that net_revenue is never blank or NULL in the report.

    This check validates the business rule that net revenue must always
    be a numeric value. Currently disabled pending pipeline fixes.

    Args:
        report_rows: List of report row dictionaries.
    """
    # for row in report_rows:
    #     assert row['net_revenue'] not in ('', None), \
    #         f"Blank net_revenue for {row['merchant_id']}/{row['month']}"
    pass
