"""
Account Service - A Flask-based account management platform.

Provides web API, CLI administration tools, and bulk import/export
capabilities for managing user accounts and balances.
"""

from account_service.app import create_app

__version__ = "1.3.0"
__all__ = ["create_app"]
