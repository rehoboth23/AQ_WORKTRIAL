"""Constants and default values for the revenue analytics pipeline."""

# Default database path
DEFAULT_DB_PATH = "data/ledger.db"

# Default report output path
DEFAULT_REPORT_PATH = "report.csv"

# Category classifications
CATEGORY_INTERNAL = "internal"
CATEGORY_SUBSCRIPTION = "subscription"
CATEGORY_ONE_TIME = "one_time"

# Transaction statuses
STATUS_COMPLETED = "completed"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"

# Revenue inclusion flags
INCLUDE_IN_REVENUE = 1
EXCLUDE_FROM_REVENUE = 0

# Timezone defaults
DEFAULT_UTC_OFFSET = "-05:00"  # US Eastern Standard Time
BUSINESS_TIMEZONE = "America/New_York"

# Currency defaults
DEFAULT_CURRENCY_CODE = "USD"
DEFAULT_CONVERSION_RATE = 1.0

# Report columns
REPORT_COLUMNS = [
    "month",
    "merchant_id",
    "gross_revenue",
    "total_refunds",
    "net_revenue",
    "transaction_count",
]

# Date formats
MONTH_FORMAT = "%Y-%m"
DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Known categories that map to include_in_revenue rules
CATEGORY_RULE_DEFAULTS = {
    CATEGORY_INTERNAL: EXCLUDE_FROM_REVENUE,
    CATEGORY_SUBSCRIPTION: INCLUDE_IN_REVENUE,
    CATEGORY_ONE_TIME: INCLUDE_IN_REVENUE,
}
