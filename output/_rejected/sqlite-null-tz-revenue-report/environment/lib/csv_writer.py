"""CSV output writer for the revenue analytics pipeline.

Handles writing report data to CSV files with proper formatting
and header generation.
"""

import csv
from lib.constants import REPORT_COLUMNS


def write_report(rows, path="report.csv"):
    """Write report rows to a CSV file.

    Args:
        rows: List of dictionaries with report data.
        path: Output file path.

    Raises:
        IOError: If the file cannot be written.
    """
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_report(path="report.csv"):
    """Read a report CSV file back into a list of dictionaries.

    Args:
        path: Path to the CSV file.

    Returns:
        List of OrderedDict rows from the CSV.
    """
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)
