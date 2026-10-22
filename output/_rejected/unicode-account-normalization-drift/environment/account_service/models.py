"""Data models for the account service.

Defines the data structures used to represent accounts and their
balance history. These are simple dataclass-based models that map
to the database schema.

Schema:
    Account:
      - id: Integer primary key
      - username: Text, unique. Username is stored in NFC form.
      - balance: Real, default 0.0
      - created_at: Text (ISO 8601 timestamp)

    BalanceHistory:
      - id: Integer primary key
      - account_id: Integer foreign key -> accounts.id
      - username: Text
      - old_balance: Real
      - new_balance: Real
      - operation: Text (deposit, withdrawal, adjustment, import)
      - created_at: Text (ISO 8601 timestamp)
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Account:
    """Represents a user account in the system.

    Attributes:
        id: The unique integer identifier for the account.
        username: The account username. Username is stored in NFC form.
        balance: The current account balance.
        created_at: ISO 8601 timestamp of account creation.
    """
    id: int
    username: str
    balance: float
    created_at: str

    @classmethod
    def from_row(cls, row):
        """Create an Account instance from a database row.

        Args:
            row: A sqlite3.Row or dict-like object with account fields.

        Returns:
            An Account instance, or None if the row is None.
        """
        if row is None:
            return None
        if isinstance(row, dict):
            return cls(
                id=row['id'],
                username=row['username'],
                balance=row['balance'],
                created_at=row['created_at'],
            )
        return cls(
            id=row[0],
            username=row[1],
            balance=row[2],
            created_at=row[3],
        )

    def to_dict(self):
        """Convert to a dictionary for JSON serialization.

        Returns:
            A dict representation of the account.
        """
        return {
            'id': self.id,
            'username': self.username,
            'balance': self.balance,
            'created_at': self.created_at,
        }


@dataclass
class BalanceHistory:
    """Represents a balance change event for an account.

    Every time an account's balance changes, a history entry is
    created recording the old and new balances and the operation
    that caused the change.

    Attributes:
        id: The unique integer identifier for the history entry.
        account_id: The ID of the account this entry belongs to.
        username: The username at the time of the operation.
        old_balance: The balance before the operation.
        new_balance: The balance after the operation.
        operation: The type of operation that caused the change.
        created_at: ISO 8601 timestamp of the operation.
    """
    id: int
    account_id: int
    username: str
    old_balance: float
    new_balance: float
    operation: str
    created_at: str

    @classmethod
    def from_row(cls, row):
        """Create a BalanceHistory instance from a database row.

        Args:
            row: A sqlite3.Row or dict-like object with history fields.

        Returns:
            A BalanceHistory instance, or None if the row is None.
        """
        if row is None:
            return None
        if isinstance(row, dict):
            return cls(
                id=row['id'],
                account_id=row['account_id'],
                username=row['username'],
                old_balance=row['old_balance'],
                new_balance=row['new_balance'],
                operation=row['operation'],
                created_at=row['created_at'],
            )
        return cls(
            id=row[0],
            account_id=row[1],
            username=row[2],
            old_balance=row[3],
            new_balance=row[4],
            operation=row[5],
            created_at=row[6],
        )

    def to_dict(self):
        """Convert to a dictionary for JSON serialization.

        Returns:
            A dict representation of the history entry.
        """
        return {
            'id': self.id,
            'account_id': self.account_id,
            'username': self.username,
            'old_balance': self.old_balance,
            'new_balance': self.new_balance,
            'operation': self.operation,
            'created_at': self.created_at,
        }
