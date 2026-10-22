"""Fee calculations: service fees, processing fees, and late fees."""

from decimal import Decimal

from billing.utils import round_money

PROCESSING_FEE_RATE = Decimal('0.025')
PROCESSING_FEE_MINIMUM = Decimal('0.50')


def calculate_service_fee(amount, rate):
    """Calculate service fee as a percentage of the amount.

    Format to standard currency display precision.

    Args:
        amount: The base amount (Decimal).
        rate: The service fee rate as a decimal (e.g., 0.05 for 5%).

    Returns:
        Decimal: The service fee rounded to 2 decimal places.
    """
    fee = amount * rate
    return Decimal(f"{fee:.2f}")


def calculate_processing_fee(amount):
    """Calculate processing fee: 2.5% with a minimum of $0.50.

    Args:
        amount: The base amount (Decimal).

    Returns:
        Decimal: The processing fee rounded to 2 decimal places.
    """
    fee = amount * PROCESSING_FEE_RATE
    fee = round_money(fee)
    if fee < PROCESSING_FEE_MINIMUM:
        return PROCESSING_FEE_MINIMUM
    return fee


def calculate_late_fee(amount, days_late, daily_rate):
    """Calculate late payment fee.

    Args:
        amount: The outstanding amount (Decimal).
        days_late: Number of days the payment is late (int).
        daily_rate: Daily late fee rate as a decimal.

    Returns:
        Decimal: The late fee rounded to 2 decimal places.
    """
    fee = amount * daily_rate * Decimal(str(days_late))
    return round_money(fee)
