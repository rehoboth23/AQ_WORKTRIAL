"""Configuration for the account service.

Default values are defined here. Runtime overrides are loaded from
the app_config database table when the Flask app is created.
"""
import os

# Unicode normalization form applied to usernames at storage and lookup time.
NORMALIZATION_FORM = 'NFD'

# Database path
DB_PATH = os.environ.get('ACCOUNT_DB_PATH', '/app/data/accounts.db')

# Flask secret key
SECRET_KEY = os.environ.get('ACCOUNT_SECRET_KEY', 'dev-secret-key-change-in-production')

# Username constraints
MAX_USERNAME_LENGTH = int(os.environ.get('MAX_USERNAME_LENGTH', '64'))
MIN_USERNAME_LENGTH = 1

# Balance constraints
MIN_BALANCE = float(os.environ.get('MIN_BALANCE', '-1000.0'))
MAX_BALANCE = float(os.environ.get('MAX_BALANCE', '999999999.0'))

# Server settings
HOST = os.environ.get('ACCOUNT_HOST', '0.0.0.0')
PORT = int(os.environ.get('ACCOUNT_PORT', '5000'))
DEBUG = os.environ.get('ACCOUNT_DEBUG', 'false').lower() in ('true', '1', 'yes')

# Rate limiting (requests per minute per endpoint)
RATE_LIMIT_REGISTER = int(os.environ.get('RATE_LIMIT_REGISTER', '5'))
RATE_LIMIT_LOGIN = int(os.environ.get('RATE_LIMIT_LOGIN', '20'))
RATE_LIMIT_ADMIN = int(os.environ.get('RATE_LIMIT_ADMIN', '10'))
