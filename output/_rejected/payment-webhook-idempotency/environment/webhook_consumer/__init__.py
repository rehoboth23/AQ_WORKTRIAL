"""Payment webhook consumer for PayStream delivery notifications.

Receives payment delivery notifications, processes them with idempotent
balance updates, and provides reconciliation against expected values.
"""

__version__ = "1.2.0"
