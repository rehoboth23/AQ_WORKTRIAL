"""Payment processor that applies pending deliveries to account balances.

For each pending delivery the processor:
1. Checks the event dedup cache to skip already-processed events.
2. Applies the payment amount to the account balance.
3. Records the event in processed_events for future dedup checks.
4. Marks the delivery as processed.

Each step is committed independently so that partial progress is
preserved if the process is interrupted.
"""

import sys
from webhook_consumer.dedup import EventDedup


class PaymentProcessor:
    """Processes pending payment deliveries and updates account balances.

    Args:
        conn: Active database connection.
        crash_after_balance: If True, exit immediately after committing
            the first balance update (for crash-recovery testing).
        crash_after_event: If True, exit immediately after committing
            the first event record (for crash-recovery testing).
    """

    def __init__(self, conn, crash_after_balance=False, crash_after_event=False):
        self.conn = conn
        self.dedup = EventDedup(conn)
        self.crash_after_balance = crash_after_balance
        self.crash_after_event = crash_after_event

    def _apply_payment(self, account_id, amount):
        """Apply a payment amount to an account's balance.

        Updates the account balance and commits the change immediately
        so that partial progress is preserved on failure.

        Args:
            account_id: The account to update.
            amount: The amount to add (negative for refunds).
        """
        self.conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE account_id = ?",
            (amount, account_id)
        )
        self.conn.commit()

    def _record_event(self, event_id):
        """Record that an event has been processed for idempotency.

        Uses INSERT OR IGNORE so that a duplicate insert is harmless.

        Args:
            event_id: The event identifier to record.
        """
        self.conn.execute(
            "INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)",
            (event_id,)
        )

    def _mark_delivered(self, delivery_id):
        """Mark a delivery as processed.

        Args:
            delivery_id: The delivery to mark.
        """
        self.conn.execute(
            "UPDATE deliveries SET status = 'processed' WHERE delivery_id = ?",
            (delivery_id,)
        )

    def process_pending(self):
        """Process all pending deliveries in the queue.

        Iterates through pending deliveries in receive order. For each
        delivery, if the event has not yet been processed, the payment
        is applied to the account balance, the event is recorded, and
        the delivery is marked as processed. If the event was already
        processed (e.g. by a concurrent consumer), the delivery is
        simply marked as processed and skipped.
        """
        deliveries = self.conn.execute(
            "SELECT delivery_id, event_id, account_id, amount "
            "FROM deliveries WHERE status = 'pending' "
            "ORDER BY received_at"
        ).fetchall()

        for row in deliveries:
            delivery_id = row[0]
            event_id = row[1]
            account_id = row[2]
            amount = row[3]

            # Skip events that were already processed (dedup check)
            if self.dedup.is_processed(event_id):
                self._mark_delivered(delivery_id)
                self.conn.commit()
                continue

            # Apply the payment to the account balance
            self._apply_payment(account_id, amount)

            # Crash simulation: exit after balance commit but before
            # the event is recorded, leaving partial state.
            if self.crash_after_balance:
                sys.exit(0)

            # Record the processed event for future dedup checks
            self._record_event(event_id)
            self.conn.commit()

            # Crash simulation: exit after event record commit
            if self.crash_after_event:
                sys.exit(0)

            # Mark the delivery as processed
            self._mark_delivered(delivery_id)
            self.conn.commit()
