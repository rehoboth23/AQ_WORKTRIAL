"""Reconciliation tool for verifying account balances against expected values.

The expected balance for each account is computed from its initial_balance
plus the sum of amounts for each unique event_id in the deliveries table.
If an event has multiple deliveries (original + retries), only one amount
is counted.
"""

import math


class Reconciler:
    """Compares actual account balances to expected values derived from events.

    Args:
        conn: Active database connection.
    """

    def __init__(self, conn):
        self.conn = conn

    def reconcile(self):
        """Check all accounts and return a list of discrepancies.

        For each account, computes:

            expected = initial_balance + sum(amount for each distinct event_id)

        and compares it to the current balance. A discrepancy is reported
        when the two differ by more than a small tolerance.

        Returns:
            List of dicts with keys: account_id, name, current_balance,
            expected_balance, difference.  Empty list if all balances match.
        """
        discrepancies = []
        accounts = self.conn.execute(
            "SELECT account_id, name, balance, initial_balance FROM accounts"
        ).fetchall()

        for account in accounts:
            account_id = account[0]
            name = account[1]
            current_balance = account[2]
            initial_balance = account[3]

            # Sum one amount per unique event_id for this account.
            # Retries share the same event_id, so GROUP BY picks one row.
            events = self.conn.execute(
                "SELECT event_id, amount FROM deliveries "
                "WHERE account_id = ? GROUP BY event_id",
                (account_id,)
            ).fetchall()

            event_total = sum(event[1] for event in events)
            expected = initial_balance + event_total

            if not math.isclose(current_balance, expected, rel_tol=1e-9, abs_tol=0.01):
                discrepancies.append({
                    "account_id": account_id,
                    "name": name,
                    "current_balance": current_balance,
                    "expected_balance": expected,
                    "difference": current_balance - expected,
                })

        return discrepancies
