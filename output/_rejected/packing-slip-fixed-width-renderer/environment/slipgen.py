#!/usr/bin/env python3
"""
slipgen - Packing Slip Generator

Generates formatted packing slips from order CSV files.

Usage:
    python3 slipgen.py generate --input orders.csv
    python3 slipgen.py generate --output slips.txt --company "ACME Corp"
    python3 slipgen.py generate --dry-run --verbose
    python3 slipgen.py stats --input orders.csv
"""

import argparse
import csv
import sys
from collections import defaultdict


# ── Configuration ────────────────────────────────────────────────────────────

REQUIRED_HEADERS = [
    'order_id', 'sku', 'quantity', 'unit_weight',
    'ship_name', 'ship_street', 'ship_city',
    'ship_region', 'ship_postal', 'ship_country'
]

DEFAULT_INPUT = '/app/orders.csv'
SLIP_SEPARATOR = '----------'

# Item line column widths
COL_SKU_WIDTH = 20
COL_QTY_WIDTH = 4
COL_WEIGHT_WIDTH = 8

# Month name abbreviations
MONTH_ABBREVS = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
]


# ── Utility Functions ────────────────────────────────────────────────────────

def safe_int(value, default=0):
    """Safely convert a value to int, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """Safely convert a value to float, returning default on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def ljust_field(text, width):
    """Left-justify text to a given character width."""
    return text.ljust(width)


def rjust_field(text, width):
    """Right-justify text to a given character width."""
    return text.rjust(width)


def center_field(text, width):
    """Center text within a given character width."""
    return text.center(width)


def format_weight_kg(value, decimals=3):
    """Format a weight value with specified decimal places and kg unit.

    Uses Python's built-in round() for rounding.
    """
    rounded = round(value, decimals)
    return f"{rounded:.{decimals}f} kg"


def validate_quantity(qty_str):
    """Validate and convert a quantity string to int.

    Raises ValueError if the quantity is negative.
    """
    qty = safe_int(qty_str)
    if qty < 0:
        raise ValueError(f"Negative quantity not allowed: {qty}")
    return qty


def parse_ship_date(date_str):
    """Parse a ship date string from the CSV.

    Returns the raw string value for display, or None if empty.
    """
    if not date_str:
        return None
    return date_str


def build_separator():
    """Build the separator line between slips."""
    return SLIP_SEPARATOR


# ── Data Classes ─────────────────────────────────────────────────────────────

class Item:
    """A single line item from an order CSV row.

    Attributes:
        order_id: The order this item belongs to.
        sku: Stock keeping unit identifier.
        quantity: Number of units ordered.
        unit_weight: Weight of a single unit in kg.
        ship_name: Recipient name for shipping.
        ship_street: Street address for shipping.
        ship_city: City for shipping.
        ship_region: State/region for shipping.
        ship_postal: Postal/ZIP code for shipping.
        ship_country: Country for shipping.
        description: Item description text.
        ship_date: Shipping date value from the CSV.
        row_num: Row number in the CSV (header = row 1).
    """

    __slots__ = (
        'order_id', 'sku', 'quantity', 'unit_weight',
        'ship_name', 'ship_street', 'ship_city',
        'ship_region', 'ship_postal', 'ship_country',
        'description', 'ship_date', 'row_num'
    )

    def __init__(self, order_id, sku, quantity, unit_weight,
                 ship_name, ship_street, ship_city,
                 ship_region, ship_postal, ship_country,
                 description='', ship_date=None, row_num=None):
        self.order_id = order_id
        self.sku = sku
        self.quantity = safe_int(quantity)
        self.unit_weight = safe_float(unit_weight)
        self.ship_name = ship_name
        self.ship_street = ship_street
        self.ship_city = ship_city
        self.ship_region = ship_region
        self.ship_postal = ship_postal
        self.ship_country = ship_country
        self.description = description or ''
        self.ship_date = ship_date
        self.row_num = row_num

        if self.quantity < 0:
            raise ValueError(
                f"Negative quantity not allowed: {self.quantity}"
            )

    @classmethod
    def from_csv_row(cls, row, has_description=False,
                     has_ship_date=False, row_num=None):
        """Create an Item from a CSV DictReader row dict."""
        return cls(
            order_id=row.get('order_id', ''),
            sku=row.get('sku', ''),
            quantity=row.get('quantity', '0'),
            unit_weight=row.get('unit_weight', '0'),
            ship_name=row.get('ship_name', ''),
            ship_street=row.get('ship_street', ''),
            ship_city=row.get('ship_city', ''),
            ship_region=row.get('ship_region', ''),
            ship_postal=row.get('ship_postal', ''),
            ship_country=row.get('ship_country', ''),
            description=row.get('description', '')
                if has_description else '',
            ship_date=parse_ship_date(row.get('ship_date', ''))
                if has_ship_date else None,
            row_num=row_num
        )

    @property
    def item_weight(self):
        """Total weight for this line item: quantity * unit_weight."""
        return self.quantity * self.unit_weight

    def formatted_weight(self):
        """Item weight formatted to 3dp with kg unit."""
        return format_weight_kg(self.item_weight, decimals=3)

    def address_key(self):
        """Return a hashable key for grouping by shipping address."""
        return (
            self.ship_street, self.ship_city,
            self.ship_region, self.ship_postal,
            self.ship_country
        )

    def __repr__(self):
        return (
            f"Item({self.order_id!r}, {self.sku!r}, "
            f"qty={self.quantity})"
        )


class Slip:
    """A packing slip for one order shipment.

    Contains one or more items all shipping to the same address
    under the same order_id.
    """

    def __init__(self, order_id, items, address=None):
        self.order_id = order_id
        self.items = list(items)
        if address is None:
            address = {}
        self.ship_name = address.get('ship_name', '')
        self.ship_street = address.get('ship_street', '')
        self.ship_city = address.get('ship_city', '')
        self.ship_region = address.get('ship_region', '')
        self.ship_postal = address.get('ship_postal', '')
        self.ship_country = address.get('ship_country', '')
        self.ship_date = address.get('ship_date', None)

    @property
    def total_quantity(self):
        """Sum of all item quantities on this slip."""
        return sum(item.quantity for item in self.items)

    @property
    def total_weight(self):
        """Total weight: sum of pre-rounded item weights, rounded to 2dp."""
        weight = 0.0
        for item in self.items:
            weight += round(item.item_weight, 3)
        return round(weight, 2)

    @property
    def item_count(self):
        """Number of distinct line items on this slip."""
        return len(self.items)

    def get_address_dict(self):
        """Return address fields as a dictionary."""
        return {
            'ship_name': self.ship_name,
            'ship_street': self.ship_street,
            'ship_city': self.ship_city,
            'ship_region': self.ship_region,
            'ship_postal': self.ship_postal,
            'ship_country': self.ship_country,
        }

    def __repr__(self):
        return f"Slip({self.order_id!r}, {self.item_count} items)"


class SlipConfig:
    """Configuration options for slip rendering."""

    def __init__(self, company=None, verbose=False):
        self.company = company
        self.verbose = verbose


# ── CSV I/O ──────────────────────────────────────────────────────────────────

def open_csv_file(filepath):
    """Open a CSV file for reading, exiting with error on failure."""
    try:
        return open(filepath, 'r', newline='')
    except FileNotFoundError:
        print(f"Error: file not found: {filepath}",
              file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {filepath}",
              file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error: cannot open {filepath}: {e}",
              file=sys.stderr)
        sys.exit(1)


def validate_csv_headers(reader):
    """Check that all required columns are present.

    Returns True if the ship_date column is present.
    """
    if reader.fieldnames is None:
        print("Error: could not read CSV headers",
              file=sys.stderr)
        sys.exit(1)

    missing = [h for h in REQUIRED_HEADERS
               if h not in reader.fieldnames]
    if missing:
        print(f"Error: missing required columns: "
              f"{', '.join(missing)}",
              file=sys.stderr)
        sys.exit(1)

    return 'ship_date' in reader.fieldnames


def read_csv(filepath, verbose=False):
    """Read and parse the orders CSV file.

    Returns:
        tuple of (items_list, has_ship_date_flag)
    """
    f = open_csv_file(filepath)
    items = []
    has_description = False

    with f:
        reader = csv.DictReader(f)
        has_ship_date = validate_csv_headers(reader)
        has_description = 'description' in reader.fieldnames

        if verbose:
            print(f"CSV columns: "
                  f"{', '.join(reader.fieldnames)}",
                  file=sys.stderr)
            print(f"ship_date: "
                  f"{'present' if has_ship_date else 'absent'}",
                  file=sys.stderr)
            print(f"description: "
                  f"{'present' if has_description else 'absent'}",
                  file=sys.stderr)

        row_num = 1  # header row is row 1
        for row in reader:
            row_num += 1
            if verbose:
                print(f"  row {row_num}: "
                      f"order={row.get('order_id', '?')}, "
                      f"sku={row.get('sku', '?')}, "
                      f"qty={row.get('quantity', '?')}",
                      file=sys.stderr)

            try:
                item = Item.from_csv_row(
                    row,
                    has_description=has_description,
                    has_ship_date=has_ship_date,
                    row_num=row_num
                )
            except ValueError as e:
                print(f"Error on row {row_num}: {e}",
                      file=sys.stderr)
                sys.exit(1)

            items.append(item)

    return items, has_ship_date


# ── Slip Grouping ────────────────────────────────────────────────────────────

def group_slips(items, has_ship_date=False):
    """Group items into slips by order_id.

    All items with the same order_id are placed on one slip,
    using the first item's shipping address for the whole order.
    Items maintain their original CSV order within each slip.
    """
    orders = defaultdict(list)
    for item in items:
        orders[item.order_id].append(item)

    slips = []
    for order_id in orders:
        order_items = orders[order_id]
        # Use the first item's address for all items in this order
        address = {
            'ship_name': order_items[0].ship_name,
            'ship_street': order_items[0].ship_street,
            'ship_city': order_items[0].ship_city,
            'ship_region': order_items[0].ship_region,
            'ship_postal': order_items[0].ship_postal,
            'ship_country': order_items[0].ship_country,
            'ship_date': order_items[0].ship_date
                if has_ship_date else None,
        }
        slip = Slip(order_id, order_items, address)
        slips.append(slip)

    return slips


# ── Rendering ────────────────────────────────────────────────────────────────

def render_address_block(slip):
    """Render the address section of a packing slip.

    Empty address fields are omitted. Region and postal code
    are combined onto one line when at least one is present.
    Country is displayed as-is from the CSV.
    """
    lines = []

    if slip.ship_name:
        lines.append(slip.ship_name)
    if slip.ship_street:
        lines.append(slip.ship_street)
    if slip.ship_city:
        lines.append(slip.ship_city)
    if slip.ship_region or slip.ship_postal:
        region = slip.ship_region or ''
        postal = slip.ship_postal or ''
        parts = [p for p in [region, postal] if p]
        if parts:
            lines.append(' '.join(parts))
    if slip.ship_country:
        lines.append(slip.ship_country)

    return lines


def render_item_line(item):
    """Render a single item line.

    Layout: SKU(20) qty(4) weight(8) description
    All columns are padded/justified by character count.
    """
    sku_str = ljust_field(item.sku, COL_SKU_WIDTH)
    qty_str = rjust_field(str(item.quantity), COL_QTY_WIDTH)
    weight_str = rjust_field(
        item.formatted_weight(), COL_WEIGHT_WIDTH)
    desc_str = item.description

    return f"{sku_str} {qty_str} {weight_str} {desc_str}"


def render_totals_line(slip):
    """Render the totals summary line for a slip."""
    total_qty = slip.total_quantity
    total_wt = slip.total_weight
    return (f"Total items: {total_qty}, "
            f"Weight: {total_wt:.2f} kg")


def render_slip(slip, config):
    """Render a complete packing slip.

    The slip includes (in order):
    - Company name (centered, if specified)
    - Order identifier
    - Ship date (if present, shown as-is)
    - Address block
    - Separator line
    - Item lines (in CSV order)
    - Totals line
    """
    lines = []

    # Company header (centered if specified)
    if config.company:
        lines.append(center_field(config.company, 72))

    # Order identifier line
    lines.append(f"Order: {slip.order_id}")

    # Ship date (if present, shown as-is from CSV)
    if slip.ship_date:
        lines.append(f"Ship date: {slip.ship_date}")

    # Address block
    addr_lines = render_address_block(slip)
    lines.extend(addr_lines)

    # Separator between address and items
    lines.append(build_separator())

    # Item lines (in CSV order)
    for item in slip.items:
        lines.append(render_item_line(item))

    # Totals line
    lines.append(render_totals_line(slip))

    return lines


def render_all_slips(slips, config):
    """Render all packing slips with separators between them."""
    all_lines = []
    for i, slip in enumerate(slips):
        if config.verbose:
            print(f"Generating slip {i + 1}/{len(slips)} "
                  f"for order {slip.order_id}",
                  file=sys.stderr)

        slip_lines = render_slip(slip, config)

        if i > 0:
            all_lines.append(build_separator())

        all_lines.extend(slip_lines)

    return all_lines


# ── Subcommands ──────────────────────────────────────────────────────────────

def cmd_generate(args):
    """Execute the 'generate' subcommand."""
    if args.verbose:
        print(f"Reading CSV from {args.input}...",
              file=sys.stderr)

    items, has_ship_date = read_csv(
        args.input, verbose=args.verbose)

    if not items:
        print("Error: no orders found in CSV",
              file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Read {len(items)} item rows from CSV",
              file=sys.stderr)

    slips = group_slips(items, has_ship_date)

    if args.verbose:
        print(f"Grouped into {len(slips)} slips",
              file=sys.stderr)

    # Dry run: report count without generating output
    if args.dry_run:
        print(f"Would generate {len(slips)} slips",
              file=sys.stderr)
        sys.exit(0)

    # Full generation
    config = SlipConfig(
        company=args.company,
        verbose=args.verbose
    )
    all_lines = render_all_slips(slips, config)
    output_text = '\n'.join(all_lines) + '\n'

    # Write output
    if args.output:
        if args.verbose:
            print(f"Writing output to {args.output}",
                  file=sys.stderr)
        with open(args.output, 'w') as out_f:
            out_f.write(output_text)
    else:
        sys.stdout.write(output_text)


def cmd_stats(args):
    """Execute the 'stats' subcommand.

    Displays summary statistics about the orders in the CSV file.
    """
    items, _ = read_csv(args.input)

    if not items:
        print("Error: no orders found in CSV",
              file=sys.stderr)
        sys.exit(1)

    order_ids = set(item.order_id for item in items)
    num_orders = len(order_ids)
    num_items = len(items)
    total_weight = sum(
        item.quantity * item.unit_weight for item in items
    )

    print(f"Orders: {num_orders}")
    print(f"Items: {num_items}")
    print(f"Total weight: {total_weight:.2f} kg")


# ── Argument Parsing ─────────────────────────────────────────────────────────

def build_parser():
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog='slipgen',
        description='Packing Slip Generator'
    )
    subparsers = parser.add_subparsers(
        dest='command', help='Available commands'
    )

    # ── generate ──
    gen = subparsers.add_parser(
        'generate',
        help='Generate packing slips from a CSV file'
    )
    gen.add_argument(
        '--input', default=DEFAULT_INPUT,
        help=f'Input CSV file (default: {DEFAULT_INPUT})'
    )
    gen.add_argument(
        '--output', default=None,
        help='Write output to file instead of stdout'
    )
    gen.add_argument(
        '--company', default=None,
        help='Company name for slip header'
    )
    gen.add_argument(
        '--dry-run', action='store_true',
        help='Print slip count without generating output'
    )
    gen.add_argument(
        '--verbose', action='store_true',
        help='Print progress info to stderr'
    )
    gen.set_defaults(func=cmd_generate)

    # ── stats ──
    stats = subparsers.add_parser(
        'stats',
        help='Display order statistics'
    )
    stats.add_argument(
        '--input', default=DEFAULT_INPUT,
        help=f'Input CSV file (default: {DEFAULT_INPUT})'
    )
    stats.set_defaults(func=cmd_stats)

    return parser


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    """Main entry point for the slipgen tool."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
