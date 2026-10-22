# Contributing to Account Service

Thank you for your interest in contributing to the Account Service project.
This document outlines the development guidelines and conventions that all
contributors should follow.

## Development Setup

1. Clone the repository
2. Install dependencies: `pip install -e .`
3. The database is automatically initialized at `/app/data/accounts.db`
4. Run the service: `flask --app account_service.app run --port 5000`

## Code Style

- Follow PEP 8 for Python code
- Use descriptive variable names that convey intent
- Add docstrings to all public functions and classes
- Keep functions focused on a single responsibility
- Prefer explicit imports over wildcard imports

## Unicode Handling

All usernames must be stored in a single, consistent Unicode normalization
form. This ensures that visually identical usernames always resolve to the same
account, preventing duplicate accounts that look the same on screen but differ
in their internal Unicode representation.

Guidelines:
- Use `normalize_for_storage()` from `normalize.py` when processing usernames
  at any entry point (web API, CLI, import)
- Always normalize usernames *before* checking for duplicates or storing
- Display names should use the same canonical form as storage for consistency
- ASCII-only usernames are unaffected by Unicode normalization
- Test with accented characters (e.g., café, naïve, Björk) to verify proper
  normalization

## Database Conventions

- Use parameterized queries to prevent SQL injection
- Always use transactions for operations that modify multiple tables
- The `balance_history` table must be kept in sync with the `accounts` table
- Every balance change must have a corresponding history entry
- Foreign key constraints are enabled; handle cascade operations carefully

## API Design

- REST endpoints should return JSON responses
- Use appropriate HTTP status codes:
  - 200: Success
  - 201: Created
  - 400: Bad request / validation error
  - 401: Unauthorized
  - 404: Not found
  - 409: Conflict (e.g., duplicate username)
- Include meaningful error messages in the response body
- Support both JSON and form-encoded request bodies where appropriate

## Testing

- Write tests for all new features
- Test edge cases including Unicode usernames with combining characters
- Ensure ASCII usernames are completely unaffected by normalization changes
- Test empty and whitespace-only inputs
- Verify that visually identical usernames in different normalization forms
  are treated as the same account

## Pull Request Process

1. Create a feature branch from main
2. Make your changes with appropriate tests
3. Ensure all existing tests still pass
4. Submit a pull request with a clear description of the changes
5. Address any review feedback before merging
