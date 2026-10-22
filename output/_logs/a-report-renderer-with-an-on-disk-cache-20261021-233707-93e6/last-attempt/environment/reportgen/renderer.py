"""HTML report renderer for ReportForge.

Produces a complete HTML document by substituting computed values into
the report template.  Template placeholders:

    ``{{heading}}``      — report heading text
    ``{{date_range}}``   — human-readable date range
    ``{{rows}}``         — HTML table rows (one per transaction)
    ``{{total}}``        — formatted grand total
"""

import html


def render_report(template, data, products, rates, settings):
    """Render an HTML report.

    Parameters
    ----------
    template : str
        HTML template with ``{{…}}`` placeholders.
    data : list[dict]
        Filtered CSV rows (date, product_id, quantity, unit_price, currency).
    products : dict
        Product catalog  ``{id: {name: …}}``.
    rates : dict
        Exchange rates   ``{code: {to_usd: …, name: …}}``.
    settings : dict
        Merged formatting settings (currency_symbol, decimal_places, …).

    Returns
    -------
    str
        Complete HTML document.
    """
    currency_symbol = settings.get("currency_symbol", "$")
    decimal_places = int(settings.get("decimal_places", 2))

    total = 0.0
    rows_html = []

    for row in data:
        date_str = row.get("date", "")
        product_id = row.get("product_id", "")
        quantity = _parse_float(row.get("quantity", 0))
        unit_price = _parse_float(row.get("unit_price", 0))
        currency = row.get("currency", "US")

        product_name = _lookup_product_name(product_id, products)
        rate = _get_conversion_rate(currency, rates)
        amount_usd = quantity * unit_price * rate
        total += amount_usd

        formatted_price = format_currency(unit_price, currency_symbol, decimal_places)
        formatted_amount = format_currency(amount_usd, currency_symbol, decimal_places)

        rows_html.append(
            f"            <tr>"
            f"<td>{html.escape(date_str)}</td>"
            f"<td>{html.escape(product_name)}</td>"
            f"<td>{quantity:.0f}</td>"
            f"<td>{formatted_price}</td>"
            f"<td>{formatted_amount}</td>"
            f"</tr>"
        )

    rows_str = "\n".join(rows_html)
    formatted_total = format_currency(total, currency_symbol, decimal_places)

    # Date range label
    if data:
        date_range = f"{data[0]['date']} to {data[-1]['date']}"
    else:
        date_range = "No data in range"

    # Substitute placeholders
    output = template
    output = output.replace("{{heading}}", html.escape(settings.get("heading", "Sales Report")))
    output = output.replace("{{date_range}}", html.escape(date_range))
    output = output.replace("{{rows}}", rows_str)
    output = output.replace("{{total}}", formatted_total)

    return output


def format_currency(amount, symbol, decimal_places):
    """Format *amount* as a currency string with the given *symbol*."""
    return f"{symbol}{amount:.{decimal_places}f}"


def _parse_float(value):
    """Safely coerce *value* to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _lookup_product_name(product_id, products):
    """Resolve a product name from the catalog, falling back to the ID."""
    product_info = products.get(product_id, {})
    return product_info.get("name", product_id)


def _get_conversion_rate(currency, rates):
    """Return the conversion factor to USD for *currency*."""
    rate_info = rates.get(currency, {})
    return float(rate_info.get("to_usd", 1.0))
