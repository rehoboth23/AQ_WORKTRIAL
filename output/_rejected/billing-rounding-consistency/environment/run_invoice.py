#!/usr/bin/env python3
"""Invoice runner - calculate and display invoices from sample data."""

import json
import sys
from decimal import Decimal
from pathlib import Path

from billing import (
    calculate_subtotal,
    calculate_line_tax,
    calculate_line_total,
    calculate_tax,
    calculate_total,
    calculate_volume_discount,
    calculate_loyalty_discount,
    calculate_early_payment_discount,
    calculate_service_fee,
    calculate_processing_fee,
    calculate_late_fee,
    calculate_surcharge,
    calculate_bulk_discount,
    calculate_additional_tax,
    calculate_compound_tax,
    calculate_withholding,
)


def load_invoices():
    """Load invoice data from the sample JSON file."""
    invoices_path = Path(__file__).parent / 'invoices' / 'sample.json'
    with open(invoices_path) as f:
        return json.load(f)


def run_invoice(invoice_id):
    """Calculate and display an invoice.

    Args:
        invoice_id: The invoice ID to process.

    Returns:
        dict: The calculated invoice amounts.
    """
    invoices = load_invoices()

    if invoice_id not in invoices:
        print(f"Invoice {invoice_id} not found.")
        sys.exit(1)

    inv = invoices[invoice_id]

    # Parse line items
    items = []
    for item in inv.get('items', []):
        items.append({
            'description': item['description'],
            'quantity': item['quantity'],
            'unit_price': Decimal(item['unit_price']),
        })

    # Calculate subtotal
    subtotal = calculate_subtotal(items)

    # Calculate primary tax
    tax_rate = Decimal(inv.get('tax_rate', '0'))
    tax_exempt = inv.get('tax_exempt', False)
    if tax_exempt:
        tax = calculate_tax(subtotal, tax_rate, tax_exempt=True)
    elif tax_rate != 0:
        tax = calculate_line_tax(subtotal, tax_rate)
    else:
        tax = Decimal('0.00')

    # Calculate discounts
    discount = Decimal('0.00')
    discount_type = inv.get('discount_type', '')
    if discount_type == 'volume':
        discount = calculate_volume_discount(
            subtotal, Decimal(inv.get('discount_rate', '0'))
        )
    elif discount_type == 'loyalty':
        discount = calculate_loyalty_discount(
            subtotal, Decimal(inv.get('discount_rate', '0'))
        )
    elif discount_type == 'early_payment':
        days_early = inv.get('days_early', 0)
        rate_per_day = Decimal(inv.get('discount_rate', '0'))
        discount = calculate_early_payment_discount(subtotal, days_early, rate_per_day)

    # Calculate fees
    fees = Decimal('0.00')
    fee_type = inv.get('fee_type', '')
    if fee_type == 'service':
        fees = calculate_service_fee(
            subtotal, Decimal(inv.get('fee_rate', '0'))
        )
    elif fee_type == 'processing':
        fees = calculate_processing_fee(subtotal)
    elif fee_type == 'late':
        days_late = inv.get('days_late', 0)
        daily_rate = Decimal(inv.get('fee_rate', '0'))
        fees = calculate_late_fee(subtotal, days_late, daily_rate)

    # Calculate surcharges
    surcharge = Decimal('0.00')
    surcharge_rate_str = inv.get('surcharge_rate', '0')
    if surcharge_rate_str and Decimal(surcharge_rate_str) != 0:
        surcharge = calculate_surcharge(subtotal, Decimal(surcharge_rate_str))

    # Calculate additional taxes
    additional_tax = Decimal('0.00')
    additional_tax_rate_str = inv.get('additional_tax_rate', '0')
    if additional_tax_rate_str and Decimal(additional_tax_rate_str) != 0:
        additional_tax = calculate_additional_tax(
            subtotal, Decimal(additional_tax_rate_str)
        )

    # Calculate total
    total_tax = tax + additional_tax
    total_fees = fees + surcharge
    total = calculate_total(subtotal, total_tax, discount, total_fees)

    # Display invoice
    print(f"{'=' * 48}")
    print(f"  INVOICE: {invoice_id}")
    if 'customer' in inv:
        print(f"  Customer: {inv['customer']}")
    print(f"{'=' * 48}")

    for item in items:
        line = calculate_line_total(item['quantity'], item['unit_price'])
        qty = item['quantity']
        price = item['unit_price']
        print(
            f"  {item['description']:30s}  {qty:3d} x "
            f"${price:>7.2f}  = ${line:>8.2f}"
        )

    print(f"{'-' * 48}")
    print(f"  {'Subtotal':30s}  ${subtotal:>9.2f}")
    print(f"  {'Tax':30s}  ${tax:>9.2f}")

    if discount > 0:
        print(f"  {'Discount':30s} -${discount:>8.2f}")
    if fees > 0:
        print(f"  {'Fees':30s}  ${fees:>9.2f}")
    if surcharge > 0:
        print(f"  {'Surcharge':30s}  ${surcharge:>9.2f}")
    if additional_tax > 0:
        print(f"  {'Additional Tax':30s}  ${additional_tax:>9.2f}")

    print(f"{'=' * 48}")
    print(f"  {'TOTAL':30s}  ${total:>9.2f}")
    print(f"{'=' * 48}")

    return {
        'subtotal': subtotal,
        'tax': tax,
        'discount': discount,
        'fees': fees,
        'surcharge': surcharge,
        'additional_tax': additional_tax,
        'total': total,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_invoice.py <invoice_id>")
        print("Available invoices can be found in invoices/sample.json")
        sys.exit(1)
    run_invoice(sys.argv[1])
