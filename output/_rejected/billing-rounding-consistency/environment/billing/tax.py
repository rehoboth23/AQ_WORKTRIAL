"""Tax calculations: additional taxes, compound taxes, and withholding."""

from decimal import Decimal, ROUND_FLOOR

from billing.utils import round_money


def calculate_additional_tax(amount, rate):
    """Calculate additional regulatory tax.

    Floor rounding to avoid over-collection of tax.

    Args:
        amount: The base amount (Decimal).
        rate: The additional tax rate as a decimal (e.g., 0.125 for 12.5%).

    Returns:
        Decimal: The additional tax rounded to 2 decimal places.
    """
    tax = amount * rate
    # Convert to cents, floor, convert back
    cents = (tax * 100).to_integral_value(rounding=ROUND_FLOOR)
    return cents / 100


def calculate_compound_tax(amount, rate1, rate2):
    """Calculate compound tax with two rates applied sequentially.

    First rate is applied to the base amount, then second rate
    is applied to the amount including the first tax.

    Args:
        amount: The base amount (Decimal).
        rate1: The first tax rate as a decimal.
        rate2: The second tax rate as a decimal.

    Returns:
        Decimal: The total compound tax rounded to 2 decimal places.
    """
    first_tax = round_money(amount * rate1)
    second_tax = round_money((amount + first_tax) * rate2)
    return first_tax + second_tax


def calculate_withholding(amount, rate):
    """Calculate tax withholding amount.

    Args:
        amount: The base amount (Decimal).
        rate: The withholding rate as a decimal.

    Returns:
        Decimal: The withholding amount rounded to 2 decimal places.
    """
    withholding = amount * rate
    return round_money(withholding)
