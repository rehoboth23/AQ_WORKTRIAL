"""Discount calculations: volume, loyalty, and early payment discounts."""

from decimal import Decimal, ROUND_DOWN

from billing.utils import round_money


def calculate_volume_discount(amount, rate):
    """Calculate volume discount based on order amount.

    Truncate to ensure we never over-discount the customer.

    Args:
        amount: The base amount to discount (Decimal).
        rate: The discount rate as a decimal (e.g., 0.125 for 12.5%).

    Returns:
        Decimal: The discount amount rounded to 2 decimal places.
    """
    discount = amount * rate
    return discount.quantize(Decimal('0.01'), rounding=ROUND_DOWN)


def calculate_loyalty_discount(amount, rate):
    """Calculate loyalty program discount.

    Args:
        amount: The base amount to discount (Decimal).
        rate: The loyalty discount rate as a decimal.

    Returns:
        Decimal: The discount amount rounded to 2 decimal places.
    """
    discount = amount * rate
    return round_money(discount)


def calculate_early_payment_discount(amount, days_early, rate_per_day):
    """Calculate early payment discount.

    The discount increases with the number of days early,
    capped at a maximum rate to prevent over-discounting.

    Args:
        amount: The invoice amount (Decimal).
        days_early: Number of days the payment is early (int).
        rate_per_day: Discount rate per day as a decimal.

    Returns:
        Decimal: The discount amount rounded to 2 decimal places.
    """
    effective_rate = rate_per_day * Decimal(str(days_early))
    discount = amount * effective_rate
    return round_money(discount)
