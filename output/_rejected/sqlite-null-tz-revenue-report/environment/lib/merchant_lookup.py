"""Merchant lookup and metadata.

Provides merchant information for display and regional analysis.
Used by the pipeline for merchant identification and by the
v_merchant_region_summary view for regional breakdowns.
"""

# Merchant registry
MERCHANTS = {
    "M001": {"name": "Alpha Corp", "region": "northeast", "onboarded": "2023-06-15"},
    "M002": {"name": "Beta LLC", "region": "west", "onboarded": "2023-08-22"},
    "M003": {"name": "Gamma Inc", "region": "midwest", "onboarded": "2023-11-01"},
    "M004": {"name": "Delta Ltd", "region": "south", "onboarded": "2024-01-10"},
}


def get_merchant_name(merchant_id):
    """Get the display name for a merchant.

    Args:
        merchant_id: The merchant identifier string.

    Returns:
        Human-readable merchant name, or 'Unknown'.
    """
    return MERCHANTS.get(merchant_id, {}).get("name", "Unknown")


def get_merchant_region(merchant_id):
    """Get the region for a merchant.

    Args:
        merchant_id: The merchant identifier string.

    Returns:
        Region string, or 'unknown'.
    """
    return MERCHANTS.get(merchant_id, {}).get("region", "unknown")


def is_merchant_active(merchant_id, as_of_date=None):
    """Check if a merchant was active as of a given date.

    A merchant is considered active if they were onboarded on or
    before the specified date.

    Args:
        merchant_id: The merchant identifier string.
        as_of_date: Date string in YYYY-MM-DD format. If None, all
                    known merchants are considered active.

    Returns:
        True if the merchant was active, False otherwise.
    """
    info = MERCHANTS.get(merchant_id)
    if not info:
        return False
    if as_of_date is None:
        return True
    return info["onboarded"] <= as_of_date


def list_merchants_by_region(region):
    """List all merchant IDs in a given region.

    Args:
        region: Region string to filter by.

    Returns:
        List of merchant IDs in the specified region.
    """
    return [
        mid for mid, info in MERCHANTS.items() if info.get("region") == region
    ]


def get_all_merchant_ids():
    """Return all known merchant IDs.

    Returns:
        List of merchant identifier strings.
    """
    return list(MERCHANTS.keys())


def get_active_merchants(as_of_date):
    """Return all merchant IDs that were active as of a date.

    Args:
        as_of_date: Date string in YYYY-MM-DD format.

    Returns:
        List of active merchant IDs.
    """
    return [
        mid
        for mid, info in MERCHANTS.items()
        if info["onboarded"] <= as_of_date
    ]
