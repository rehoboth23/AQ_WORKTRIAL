"""Custom exceptions for the account service.

Defines a hierarchy of exception classes that represent different
types of errors that can occur in the account service. These are
caught by the error handling decorators and converted to appropriate
HTTP responses.
"""


class AccountServiceError(Exception):
    """Base exception for account service.

    All service-specific exceptions inherit from this class,
    making it easy to catch all service errors at once.
    """
    pass


class AccountNotFoundError(AccountServiceError):
    """Account not found in the database.

    Raised when an operation references an account that does not exist.
    Maps to HTTP 404.
    """
    pass


class DuplicateUsernameError(AccountServiceError):
    """Username already exists.

    Raised when attempting to create an account with a username
    that is already taken. Maps to HTTP 409.
    """
    pass


class InvalidUsernameError(AccountServiceError):
    """Username validation failed.

    Raised when a username does not meet format requirements.
    Maps to HTTP 400.
    """
    pass


class InsufficientBalanceError(AccountServiceError):
    """Insufficient balance for withdrawal.

    Raised when a withdrawal would bring the balance below
    the allowed minimum. Maps to HTTP 400.
    """
    pass


class InvalidOperationError(AccountServiceError):
    """Invalid balance operation.

    Raised when an operation is not recognized or its parameters
    are invalid. Maps to HTTP 400.
    """
    pass


class ConfigurationError(AccountServiceError):
    """Configuration error.

    Raised when a required configuration value is missing or invalid.
    Maps to HTTP 500.
    """
    pass


class DatabaseError(AccountServiceError):
    """Database operation error.

    Raised when a database operation fails unexpectedly.
    Maps to HTTP 500.
    """
    pass
