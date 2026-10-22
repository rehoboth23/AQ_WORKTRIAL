"""Utility functions for monetary calculations.

Provides the standard rounding function used throughout the billing
module. All monetary amounts must be rounded to 2 decimal places
using round-half-up (standard business rounding).
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal('0.01')


def round_money(amount):
    """Round a monetary amount to 2 decimal places using round-half-up.

    Standard business rounding: when a value is exactly halfway
    between two possibilities, it rounds away from zero.

    Args:
        amount: A Decimal value to round.

    Returns:
        Decimal: The amount rounded to 2 decimal places with ROUND_HALF_UP.
    """
    if amount is None:
        return Decimal('0.00')
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_money(amount):
    """Format a monetary amount for display.

    Rounds the amount using round_money, then formats as a string
    with 2 decimal places.

    Args:
        amount: A Decimal value to format.

    Returns:
        str: The amount formatted as a currency string.
    """
    rounded = round_money(amount)
    return f"{rounded:.2f}"
