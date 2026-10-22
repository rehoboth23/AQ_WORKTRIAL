"""Decorators for the account service.

Provides function decorators for error handling, input validation,
and request processing that are used across route handlers.
"""
import functools
from flask import jsonify, request
from account_service.exceptions import AccountServiceError


def handle_errors(f):
    """Decorator that catches service exceptions and returns appropriate HTTP responses.

    Catches AccountServiceError subclasses and converts them to JSON
    responses with the appropriate HTTP status code. Unhandled exceptions
    return a generic 500 error.

    Status code mapping:
    - AccountNotFoundError -> 404
    - DuplicateUsernameError -> 409
    - InvalidUsernameError -> 400
    - InsufficientBalanceError -> 400
    - InvalidOperationError -> 400
    - ConfigurationError -> 500
    - DatabaseError -> 500
    - Other AccountServiceError -> 400
    - Other Exception -> 500
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AccountServiceError as e:
            from account_service.exceptions import (
                AccountNotFoundError,
                DuplicateUsernameError,
                InvalidUsernameError,
                InsufficientBalanceError,
                InvalidOperationError,
                ConfigurationError,
                DatabaseError,
            )
            if isinstance(e, AccountNotFoundError):
                status = 404
            elif isinstance(e, DuplicateUsernameError):
                status = 409
            elif isinstance(e, InvalidUsernameError):
                status = 400
            elif isinstance(e, InsufficientBalanceError):
                status = 400
            elif isinstance(e, InvalidOperationError):
                status = 400
            elif isinstance(e, ConfigurationError):
                status = 500
            elif isinstance(e, DatabaseError):
                status = 500
            else:
                status = 400
            return jsonify({'error': str(e)}), status
        except Exception as e:
            return jsonify({'error': 'Internal server error'}), 500
    return wrapper


def require_json(f):
    """Decorator that requires JSON content type.

    Returns a 415 Unsupported Media Type response if the request
    does not have Content-Type: application/json.

    Returns:
        The decorated function.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 415
        return f(*args, **kwargs)
    return wrapper


def require_fields(*required_fields):
    """Decorator factory that requires specific JSON fields.

    Returns a 400 Bad Request response if any of the specified
    fields are missing from the JSON request body.

    Args:
        *required_fields: Names of required JSON fields.

    Returns:
        A decorator function.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if not data:
                return jsonify({'error': 'Request body required'}), 400
            missing = [field for field in required_fields if field not in data]
            if missing:
                return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator
