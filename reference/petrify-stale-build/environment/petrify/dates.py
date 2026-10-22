"""Parsing and display of frontmatter dates."""

from datetime import date, datetime, timezone
from email.utils import format_datetime

INPUT_FORMATS = ("%d %B %Y", "%d %b %Y")

#: Sort key for values that could not be parsed: they come after every dated
#: item in a newest-first listing.
SORT_LAST = datetime.min


def parse(value):
    """Return a ``datetime`` for a frontmatter date value.

    ``datetime`` and ``date`` objects are used directly.  Strings are tried
    against :data:`INPUT_FORMATS` in order.  Anything else, including a string
    that matches no format, yields :data:`SORT_LAST`.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in INPUT_FORMATS:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
    return SORT_LAST


def display(value):
    """``'5 January 2024'``; values that don't parse are shown as they are."""
    dt = parse(value)
    if dt is SORT_LAST:
        return "" if value is None else str(value)
    return f"{dt.day} {dt:%B %Y}"


def iso(value):
    """``YYYY-MM-DD`` for ``<time datetime>``; empty when the value doesn't parse."""
    dt = parse(value)
    return "" if dt is SORT_LAST else dt.strftime("%Y-%m-%d")


def rfc822(value):
    """RSS ``<pubDate>`` form; empty when the value doesn't parse."""
    dt = parse(value)
    return "" if dt is SORT_LAST else format_datetime(dt.replace(tzinfo=timezone.utc))
