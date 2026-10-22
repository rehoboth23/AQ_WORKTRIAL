#!/usr/bin/env python3
"""Generate monthly revenue report from the ledger database."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.config_loader import load_config
from lib.db import get_connection
from lib.report_builder import build_report
from lib.csv_writer import write_report


def main():
    config = load_config("config.yaml")
    conn = get_connection(config)
    report_rows = build_report(conn, config)
    write_report(report_rows, "report.csv")
    conn.close()
    print(f"Report generated: report.csv ({len(report_rows)} rows)")


if __name__ == "__main__":
    main()
