"""Application configuration for the payment webhook consumer."""

import os

# Database path — can be overridden via environment variable
DB_PATH = os.environ.get("PAYMENTS_DB_PATH", "/app/data/payments.db")

# PayStream provider settings
PROVIDER_NAME = "PayStream"
MAX_RETRY_DELIVERIES = 5

# Processing settings
BATCH_SIZE = 100
