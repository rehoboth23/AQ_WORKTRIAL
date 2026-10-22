# Account Service

A Flask-based account management service with web API, CLI, and bulk
import/export capabilities.

## Overview

The account service provides:
- **Web API** for account registration, authentication, and balance management
- **Admin endpoints** for balance adjustments and account management
- **CLI** for account operations and data export from the command line
- **Bulk import/export** via CSV files for batch operations

## Setup

### Prerequisites
- Python 3.12+
- Flask
- Click

### Installation

```bash
pip install -e .
```

### Configuration

Configuration is managed through multiple layers:

1. **config.py** — Default configuration values
2. **app_config database table** — Runtime overrides loaded at startup
3. **Environment variables** — For deployment-specific settings

Key settings:
- `NORMALIZATION_FORM` — Unicode normalization form for username storage
- `MAX_USERNAME_LENGTH` — Maximum username length (default: 64)
- `MIN_BALANCE` — Minimum allowed balance (default: -1000.0)

### Running the Service

```bash
# Start the web server
flask --app account_service.app run --port 5000

# Or using the CLI module
python3 -m account_service.cli --help
```

### CLI Commands

```bash
# Create an account
python3 -m account_service.cli create <username> [--balance 100]

# Look up an account
python3 -m account_service.cli lookup <username>

# Deposit funds
python3 -m account_service.cli deposit <account_id> <amount>

# Withdraw funds
python3 -m account_service.cli withdraw <account_id> <amount>

# Export accounts to CSV
python3 -m account_service.cli export <output_path>

# List all accounts
python3 -m account_service.cli list

# View balance history
python3 -m account_service.cli history <account_id>
```

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | POST | Register a new account |
| `/api/auth/login` | POST | Login with username |
| `/api/accounts/<username>/balance` | GET | Get balance |
| `/api/accounts/<username>/deposit` | POST | Deposit funds |
| `/api/accounts/<username>/withdraw` | POST | Withdraw funds |
| `/api/admin/adjust` | POST | Adjust balance (admin) |
| `/api/admin/account/<username>` | GET | Get account details |
| `/api/reports/monthly` | GET | Monthly summary report |
| `/api/health` | GET | Health check |
| `/api/health/ready` | GET | Readiness check |

## Data Model

### Account
- `id` — Integer, primary key
- `username` — Text, unique
- `balance` — Real, default 0.0
- `created_at` — Text, ISO 8601 timestamp

### BalanceHistory
- `id` — Integer, primary key
- `account_id` — Integer, foreign key
- `username` — Text
- `old_balance` — Real
- `new_balance` — Real
- `operation` — Text (deposit, withdrawal, adjustment, import)
- `created_at` — Text, ISO 8601 timestamp

## Project Structure

```
account_service/
├── __init__.py          # Package init
├── __main__.py          # Entry point for python -m
├── app.py               # Flask app factory
├── cli.py               # CLI commands
├── cli_helpers.py       # CLI utility functions
├── config.py            # Default configuration
├── db.py                # Database access layer
├── decorators.py        # Route decorators
├── error_handlers.py    # HTTP error handlers
├── exceptions.py        # Custom exceptions
├── import_export.py     # CSV import/export
├── middleware.py        # WSGI middleware
├── models.py            # Data models
├── normalize.py         # Unicode normalization utilities
├── utils.py             # General utilities
├── validation.py        # Username validation
├── _internal.py         # Internal normalization helpers
├── CONTRIBUTING.md      # Contribution guidelines
├── README.md            # This file
└── routes/
    ├── __init__.py      # Route package
    ├── auth.py          # Authentication routes
    ├── accounts.py      # Account balance routes
    ├── admin.py         # Admin routes
    ├── reports.py       # Report routes
    └── health.py        # Health check routes
```

## License

Internal use only.
