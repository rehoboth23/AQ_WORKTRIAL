"""Historical exchange rate data.

This module contains EUR/USD exchange rates that were used when the
ledger stored amounts in EUR (prior to the USD migration in late 2023).
Kept for reference and auditing purposes. The current pipeline uses
a single conversion_rate from config.yaml instead of monthly rates.
"""

HISTORICAL_RATES = {
    "2024-01": 0.847,
    "2024-02": 0.856,
    "2024-03": 0.823,
    "2023-12": 0.831,
    "2023-11": 0.862,
    "2023-10": 0.855,
    "2023-09": 0.841,
    "2023-08": 0.838,
    "2023-07": 0.829,
    "2023-06": 0.815,
    "2023-05": 0.822,
    "2023-04": 0.834,
    "2023-03": 0.827,
    "2023-02": 0.819,
    "2023-01": 0.812,
}


def get_rate(month):
    """Get the EUR/USD rate for a given month.

    Args:
        month: Month string in YYYY-MM format.

    Returns:
        Exchange rate as float, or None if not available.
    """
    return HISTORICAL_RATES.get(month)


def get_average_rate(start_month, end_month):
    """Get the average EUR/USD rate over a range of months.

    Args:
        start_month: Start month in YYYY-MM format.
        end_month: End month in YYYY-MM format.

    Returns:
        Average exchange rate, or None if no data in range.
    """
    rates = []
    year, month = map(int, start_month.split("-"))
    end_year, end_month_num = map(int, end_month.split("-"))

    while (year, month) <= (end_year, end_month_num):
        key = f"{year:04d}-{month:02d}"
        if key in HISTORICAL_RATES:
            rates.append(HISTORICAL_RATES[key])
        month += 1
        if month > 12:
            month = 1
            year += 1

    if not rates:
        return None
    return sum(rates) / len(rates)


def convert_eur_to_usd(eur_amount, month):
    """Convert a EUR amount to USD using the historical rate for a given month.

    Args:
        eur_amount: Amount in EUR.
        month: Month string in YYYY-MM format.

    Returns:
        Amount in USD, or None if rate not available.
    """
    rate = get_rate(month)
    if rate is None:
        return None
    return round(eur_amount / rate, 2)
