"""Logging configuration for the revenue analytics pipeline.

Provides consistent logging setup across all pipeline modules.
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_logger = None


def get_logger(name="revenue_analytics"):
    """Get or create the pipeline logger.

    Args:
        name: Logger name.

    Returns:
        Configured logging.Logger instance.
    """
    global _logger
    if _logger is None:
        _logger = logging.getLogger(name)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        _logger.addHandler(handler)
        _logger.setLevel(logging.INFO)
    return _logger


def set_log_level(level):
    """Set the logging level.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO).
    """
    logger = get_logger()
    logger.setLevel(level)


def log_pipeline_start(config_path="config.yaml"):
    """Log the start of a pipeline run.

    Args:
        config_path: Path to the configuration file being used.
    """
    logger = get_logger()
    logger.info(f"Pipeline started with config: {config_path}")


def log_pipeline_complete(row_count, output_path="report.csv"):
    """Log the completion of a pipeline run.

    Args:
        row_count: Number of rows in the output report.
        output_path: Path to the generated report file.
    """
    logger = get_logger()
    logger.info(f"Pipeline complete: {row_count} rows written to {output_path}")
