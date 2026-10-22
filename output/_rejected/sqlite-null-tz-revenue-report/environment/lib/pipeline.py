"""Pipeline orchestration for the revenue analytics report.

This module provides the main pipeline that coordinates data loading,
transformation, and report generation. It is designed to be extensible
with additional stages as the analytics requirements evolve.
"""

import sys
import os

from lib.config_loader import load_config
from lib.db import get_connection
from lib.report_builder import build_report
from lib.csv_writer import write_report
from lib.validators import validate_report, validate_no_duplicate_months


class PipelineResult:
    """Result of a pipeline run."""

    def __init__(self, success=True, rows=None, errors=None, warnings=None):
        self.success = success
        self.rows = rows or []
        self.errors = errors or []
        self.warnings = warnings or []

    def __repr__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"PipelineResult({status}, {len(self.rows)} rows, "
            f"{len(self.errors)} errors, {len(self.warnings)} warnings)"
        )

    def summary(self):
        """Return a human-readable summary of the pipeline result."""
        lines = [f"Status: {'SUCCESS' if self.success else 'FAILED'}"]
        lines.append(f"Rows: {len(self.rows)}")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


def run_pipeline(config_path="config.yaml", output_path="report.csv"):
    """Run the complete revenue analytics pipeline.

    Args:
        config_path: Path to the YAML configuration file.
        output_path: Path for the output CSV report.

    Returns:
        PipelineResult with success status, report rows, and any errors/warnings.
    """
    errors = []
    warnings = []

    # Stage 1: Load configuration
    try:
        config = load_config(config_path)
    except Exception as e:
        return PipelineResult(
            success=False, errors=[f"Config load error: {e}"]
        )

    # Stage 2: Connect to database
    try:
        conn = get_connection(config)
    except Exception as e:
        return PipelineResult(
            success=False, errors=[f"Database connection error: {e}"]
        )

    # Stage 3: Build report from views
    try:
        rows = build_report(conn, config)
    except Exception as e:
        conn.close()
        return PipelineResult(
            success=False, errors=[f"Report build error: {e}"]
        )

    # Stage 4: Validate (non-blocking - log warnings but continue)
    if not validate_report(rows):
        warnings.append("Report validation warnings detected")

    if not validate_no_duplicate_months(rows):
        warnings.append("Duplicate month/merchant pairs detected")

    # Stage 5: Write output
    try:
        write_report(rows, output_path)
    except Exception as e:
        conn.close()
        return PipelineResult(
            success=False, errors=[f"Report write error: {e}"]
        )

    conn.close()
    return PipelineResult(success=True, rows=rows, errors=errors, warnings=warnings)


if __name__ == "__main__":
    result = run_pipeline()
    print(result.summary())
    sys.exit(0 if result.success else 1)
