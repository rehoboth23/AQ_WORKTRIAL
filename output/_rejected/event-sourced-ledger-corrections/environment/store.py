"""Event store for the inventory ledger.

Provides the EventStore class which manages event records and tracks
effective quantities as corrections are applied over time.
"""

import json
from collections import defaultdict


class EventStore:
    """Central store for event data and effective quantity tracking.

    Maintains two key data structures:
    - events: maps event_id to the original event dict
    - effective_qty: maps event_id to its current effective quantity
      (updated when corrections are applied)

    The store also provides lookup methods for querying events by
    various criteria.
    """

    def __init__(self):
        self.events = {}                # event_id -> event dict
        self.effective_qty = {}         # event_id -> current effective quantity
        self._sku_index = defaultdict(list)  # sku -> list of event_ids

    def add_event(self, event):
        """Register an event in the store.

        For RECEIPT and SHIPMENT events, the effective quantity is
        initialized to the event's quantity field. CORRECTION events
        do not have their own effective quantity; instead they modify
        the effective quantity of the referenced event via
        update_effective_qty.

        Args:
            event: dict with event_id, type, sku, quantity, and
                   optionally ref_id (for corrections).

        Raises:
            ValueError: if the event is missing required fields.
        """
        self._validate_event(event)
        eid = event["event_id"]
        self.events[eid] = event
        if event["type"] in ("RECEIPT", "SHIPMENT"):
            self.effective_qty[eid] = event["quantity"]
        self._sku_index[event["sku"]].append(eid)

    def update_effective_qty(self, event_id, new_qty):
        """Update the effective quantity for an event after a correction.

        Args:
            event_id: the event whose effective quantity to update
            new_qty: the new effective quantity value
        """
        self.effective_qty[event_id] = new_qty

    def get_event(self, event_id):
        """Return the original event by event_id.

        Args:
            event_id: the logical event identifier

        Returns:
            The event dict, or None if not found.
        """
        return self.events.get(event_id)

    def get_effective_qty(self, event_id):
        """Return the current effective quantity for an event.

        The effective quantity starts as the event's original quantity
        and is updated each time a correction is applied to the event.

        Args:
            event_id: the logical event identifier

        Returns:
            The current effective quantity, or None if not found.
        """
        return self.effective_qty.get(event_id)

    def has_event(self, event_id):
        """Check if an event_id has been registered.

        Args:
            event_id: the logical event identifier

        Returns:
            True if the event has been registered, False otherwise.
        """
        return event_id in self.events

    def get_events_by_sku(self, sku):
        """Return all event_ids associated with a SKU.

        Args:
            sku: the SKU to look up

        Returns:
            List of event_id strings.
        """
        return list(self._sku_index.get(sku, []))

    def get_corrections_for(self, event_id):
        """Return all correction events that reference a given event.

        Args:
            event_id: the event being corrected

        Returns:
            List of correction event dicts, in insertion order.
        """
        return [
            evt for evt in self.events.values()
            if evt["type"] == "CORRECTION" and evt.get("ref_id") == event_id
        ]

    @property
    def event_count(self):
        """Return the number of registered events."""
        return len(self.events)

    def _validate_event(self, event):
        """Validate that an event has the required fields.

        Args:
            event: the event dict to validate

        Raises:
            ValueError: if required fields are missing.
        """
        required = ["event_id", "type", "sku", "quantity"]
        for field in required:
            if field not in event:
                raise ValueError(f"Event missing required field: {field}")
        if event["type"] not in ("RECEIPT", "SHIPMENT", "CORRECTION"):
            raise ValueError(f"Invalid event type: {event['type']}")
        if event["type"] == "CORRECTION" and "ref_id" not in event:
            raise ValueError("Correction event missing ref_id")

    def load_from_file(self, path):
        """Load events from a JSONL file into the store.

        Args:
            path: path to the JSONL file

        Returns:
            Number of events loaded.
        """
        count = 0
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    event = json.loads(line)
                    self.add_event(event)
                    count += 1
        return count

    def __repr__(self):
        return f"EventStore(events={self.event_count})"
