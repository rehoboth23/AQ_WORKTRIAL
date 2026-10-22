"""Bulk order calculations: surcharges and bulk discounts."""

from decimal import Decimal

from billing.utils import round_money


def calculate_surcharge(amount, rate):
    """Calculate surcharge as a percentage of the amount.

    Convert to cents for precision, then back to dollars.

    Args:
        amount: The base amount (Decimal).
        rate: The surcharge rate as a decimal (e.g., 0.125 for 12.5%).

    Returns:
        Decimal: The surcharge rounded to 2 decimal places.
    """
    surcharge = amount * rate
    # Cents conversion for precise rounding
    cents = int(surcharge * 100)
    return Decimal(cents) / 100


def calculate_bulk_discount(amount, rate):
    """Calculate bulk order discount.

    Args:
        amount: The base amount (Decimal).
        rate: The bulk discount rate as a decimal.

    Returns:
        Decimal: The discount amount rounded to 2 decimal places.
    """
    discount = amount * rate
    return round_money(discount)
