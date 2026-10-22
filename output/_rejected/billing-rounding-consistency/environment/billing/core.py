"""Core billing calculations: subtotals, line items, taxes, and totals."""

from decimal import Decimal

from billing.utils import round_money


def calculate_line_total(quantity, unit_price):
    """Calculate the total for a single line item.

    Args:
        quantity: Number of units (int or Decimal).
        unit_price: Price per unit (Decimal).

    Returns:
        Decimal: The line total rounded to 2 decimal places.
    """
    total = Decimal(str(quantity)) * unit_price
    return round_money(total)


def calculate_subtotal(items):
    """Calculate the subtotal for a list of line items.

    Each item is a dict with 'quantity' (int) and 'unit_price' (Decimal).

    Args:
        items: List of dicts with 'quantity' and 'unit_price' keys.

    Returns:
        Decimal: The subtotal rounded to 2 decimal places.
    """
    subtotal = Decimal('0')
    for item in items:
        line_total = Decimal(str(item['quantity'])) * item['unit_price']
        subtotal += line_total
    return round_money(subtotal)


def calculate_line_tax(subtotal, rate):
    """Calculate tax on a subtotal at the given rate.

    Uses standard rounding for tax amounts.

    Args:
        subtotal: The taxable amount (Decimal).
        rate: The tax rate as a decimal (e.g., 0.0625 for 6.25%).

    Returns:
        Decimal: The tax amount rounded to 2 decimal places.
    """
    tax = subtotal * rate
    return round(tax, 2)


def calculate_tax(subtotal, rate, tax_exempt=False):
    """Calculate tax with optional tax-exempt status.

    Args:
        subtotal: The taxable amount (Decimal).
        rate: The tax rate as a decimal (e.g., 0.0625 for 6.25%).
        tax_exempt: Whether the item is tax-exempt.

    Returns:
        Decimal: The tax amount, or 0.00 if tax-exempt.
    """
    if tax_exempt:
        return Decimal('0.00')
    tax = subtotal * rate
    return round_money(tax)


def calculate_total(subtotal, tax, discount, fees):
    """Calculate the final invoice total.

    total = subtotal + tax - discount + fees

    Args:
        subtotal: The subtotal amount (Decimal).
        tax: The total tax amount (Decimal).
        discount: The total discount amount (Decimal).
        fees: The total fees amount (Decimal).

    Returns:
        Decimal: The final total rounded to 2 decimal places.
    """
    total = subtotal + tax - discount + fees
    return round_money(total)
