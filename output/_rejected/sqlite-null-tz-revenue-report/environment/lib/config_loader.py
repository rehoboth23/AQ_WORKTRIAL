"""Configuration loader for the revenue analytics pipeline.

Reads YAML configuration files and provides access to pipeline settings
including database paths, currency conversion rates, and timezone info.
"""

import yaml


def load_config(path="config.yaml"):
    """Load and return the pipeline configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Dictionary containing the configuration values.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_database_path(config):
    """Extract the database path from configuration.

    Args:
        config: Loaded configuration dictionary.

    Returns:
        Path to the SQLite database file.
    """
    return config.get("database", {}).get("path", "data/ledger.db")


def get_conversion_rate(config):
    """Extract the currency conversion rate from configuration.

    Args:
        config: Loaded configuration dictionary.

    Returns:
        Conversion rate as a float.
    """
    return config.get("reporting", {}).get("currency", {}).get("conversion_rate", 1.0)


def get_currency_code(config):
    """Extract the reporting currency code from configuration.

    Args:
        config: Loaded configuration dictionary.

    Returns:
        Currency code string (e.g., 'USD', 'EUR').
    """
    return config.get("reporting", {}).get("currency", {}).get("code", "USD")


def get_utc_offset(config):
    """Extract the UTC offset from configuration.

    Args:
        config: Loaded configuration dictionary.

    Returns:
        UTC offset string (e.g., '-05:00').
    """
    return config.get("reporting", {}).get("timezone", {}).get("utc_offset", "+00:00")
