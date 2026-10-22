"""Event deduplication cache to prevent reprocessing of payment events.

The EventDedup class maintains an in-memory set of event_ids that have
already been processed, loaded from the processed_events table. This
avoids a database query on every dedup check during batch processing.
"""


class EventDedup:
    """Tracks which event_ids have already been processed.

    Uses an in-memory cache loaded from the processed_events table
    for fast lookups during batch processing. The cache is loaded
    lazily on first access and can be explicitly invalidated when
    the underlying data may have changed.
    """

    def __init__(self, conn):
        self.conn = conn
        self._cache = None

    def _load_cache(self):
        """Load all processed event_ids from the database into memory."""
        rows = self.conn.execute(
            "SELECT event_id FROM processed_events"
        ).fetchall()
        self._cache = {row[0] for row in rows}

    def is_processed(self, event_id):
        """Check whether an event_id has already been processed.

        Returns True if the event is recorded in processed_events,
        False otherwise. The cache is loaded lazily on first access.

        Args:
            event_id: The logical event identifier to check.

        Returns:
            bool indicating whether the event was already processed.
        """
        if self._cache is None:
            self._load_cache()
        return event_id in self._cache

    def invalidate(self):
        """Clear the in-memory cache, forcing a reload on next access.

        Useful when the processed_events table has been modified
        externally and the cache may be stale.
        """
        self._cache = None
