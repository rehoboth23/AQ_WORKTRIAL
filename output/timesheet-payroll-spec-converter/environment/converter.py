#!/usr/bin/env python3
"""
Timesheet to Payroll Converter

Converts employee timesheet data from CSV format into payroll
reports with overtime calculations and gross pay computations.

Usage:
    python3 converter.py <input_csv> [--summary] [--verbose]
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# ── Compensation rates ────────────────────────────────────────
REGULAR_RATE = 25.00
OVERTIME_RATE = 37.50       # 1.5x regular
DOUBLE_TIME_RATE = 50.00    # 2x regular

# ── Overtime thresholds ──────────────────────────────────────
DAILY_THRESHOLD = 8.0
WEEKLY_THRESHOLD = 40.0

# ── Timestamp format ─────────────────────────────────────────
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


class TimesheetEntry:
    """Represents a single row from the timesheet CSV.

    Each entry contains an employee ID, a clock-in timestamp,
    and optionally a clock-out timestamp. Timestamps are parsed
    from the string format used in the CSV.

    Attributes:
        employee_id: The employee identifier string.
        clock_in_str: Raw clock-in timestamp string.
        clock_out_str: Raw clock-out timestamp string (may be empty).
        clock_in: Parsed clock-in datetime.
        clock_out: Parsed clock-out datetime, or None if missing.
        valid: Whether parsing succeeded.
    """

    def __init__(self, employee_id, clock_in_str, clock_out_str):
        self.employee_id = employee_id
        self.clock_in_str = clock_in_str
        self.clock_out_str = clock_out_str
        self.clock_in = None
        self.clock_out = None
        self.valid = False
        self._parse()

    def _parse(self):
        """Parse timestamp strings into datetime objects."""
        try:
            self.clock_in = datetime.strptime(self.clock_in_str, TS_FORMAT)
            if self.clock_out_str:
                self.clock_out = datetime.strptime(self.clock_out_str, TS_FORMAT)
            self.valid = True
        except (ValueError, TypeError):
            self.valid = False

    @property
    def is_complete(self):
        """Check if the entry has both clock-in and clock-out."""
        return self.valid and self.clock_out is not None

    def __repr__(self):
        return (f"TimesheetEntry({self.employee_id!r}, "
                f"{self.clock_in_str!r}, {self.clock_out_str!r})")


class Shift:
    """Represents a matched shift with calculated duration.

    A shift is created from a complete timesheet entry and
    computes the worked duration in hours.

    Attributes:
        employee_id: The employee identifier.
        clock_in: Clock-in datetime.
        clock_out: Clock-out datetime.
        raw_duration: Exact duration in hours (float).
        rounded_duration: Rounded duration in hours.
    """

    def __init__(self, employee_id, clock_in, clock_out):
        self.employee_id = employee_id
        self.clock_in = clock_in
        self.clock_out = clock_out
        self._compute_duration()

    def _compute_duration(self):
        """Calculate shift duration in hours."""
        delta = self.clock_out - self.clock_in
        self.raw_duration = delta.total_seconds() / 3600.0
        # Round to 2 decimal places
        self.rounded_duration = round(self.raw_duration, 2)

    @property
    def date(self):
        """The calendar date of the shift start."""
        return self.clock_in.date()

    @property
    def week_start(self):
        """Compute the Monday of the week containing this shift's start.

        Uses the clock_in date to determine the work week.
        Monday is weekday 0 in Python's datetime.
        """
        d = self.clock_in.date()
        monday = d - timedelta(days=d.weekday())
        return monday

    def __repr__(self):
        return f"Shift({self.employee_id!r}, {self.rounded_duration:.2f}h)"

    def __str__(self):
        cin = self.clock_in.strftime(TS_FORMAT)
        cout = self.clock_out.strftime(TS_FORMAT)
        return f"{self.employee_id}: {cin} -> {cout} ({self.rounded_duration:.2f}h)"


class TimesheetReader:
    """Reads and parses timesheet entries from a CSV file.

    The CSV is expected to have a header row followed by data rows
    with columns: Employee ID, Clock In, Clock Out

    Blank lines are silently skipped. Whitespace around field
    values is trimmed before processing.
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self.entries = []

    def read(self):
        """Read all timesheet entries from the CSV file.

        Returns:
            List of TimesheetEntry objects.

        Exits with code 1 if the file is not found.
        """
        try:
            with open(self.filepath, 'r', newline='') as f:
                reader = csv.reader(f)
                header = None
                line_num = 0
                for row in reader:
                    line_num += 1

                    # Skip blank lines
                    if not row or all(field.strip() == '' for field in row):
                        continue

                    # Trim whitespace from all fields
                    row = [field.strip() for field in row]

                    # First non-blank row is the header
                    if header is None:
                        header = row
                        continue

                    # Need at least employee ID and clock-in
                    if len(row) < 2:
                        continue

                    employee_id = row[0]
                    clock_in_str = row[1]
                    clock_out_str = row[2] if len(row) > 2 and row[2] else ''

                    try:
                        entry = TimesheetEntry(
                            employee_id, clock_in_str, clock_out_str
                        )
                        if entry.valid:
                            self.entries.append(entry)
                        else:
                            print(f"Warning: Invalid row at line {line_num}",
                                  file=sys.stderr)
                    except Exception as e:
                        print(f"Warning: Error parsing row at line "
                              f"{line_num}: {e}", file=sys.stderr)
                        continue

        except FileNotFoundError:
            print(f"Error: File not found: {self.filepath}", file=sys.stderr)
            sys.exit(1)

        return self.entries


class ShiftMatcher:
    """Matches timesheet entries into shifts.

    Handles duplicate detection and filters out incomplete
    or invalid entries. Two entries with the same employee ID,
    clock-in string, and clock-out string are considered
    duplicates and only the first occurrence is kept.
    """

    def match(self, entries, verbose=False):
        """Process entries into valid shifts.

        Args:
            entries: List of TimesheetEntry objects.
            verbose: If True, print processing details to stderr.

        Returns:
            List of Shift objects.
        """
        shifts = []

        # Group entries by employee
        by_employee = defaultdict(list)
        for entry in entries:
            by_employee[entry.employee_id].append(entry)

        for emp_id, emp_entries in by_employee.items():
            # Deduplicate: remove exact row duplicates
            seen = set()
            unique_entries = []
            for entry in emp_entries:
                key = (entry.clock_in_str, entry.clock_out_str)
                if key not in seen:
                    seen.add(key)
                    unique_entries.append(entry)

            # Process entries into shifts
            for entry in unique_entries:
                if not entry.is_complete:
                    # Silently skip incomplete entries
                    continue

                # Validate clock-out is after clock-in
                if entry.clock_out <= entry.clock_in:
                    continue

                shift = Shift(entry.employee_id, entry.clock_in, entry.clock_out)

                # Skip zero-duration shifts
                if shift.rounded_duration > 0:
                    shifts.append(shift)

        return shifts


class PayrollEngine:
    """Computes payroll amounts from shifts.

    Groups shifts by employee and work week, then calculates
    regular hours, overtime hours, and gross pay.
    """

    def compute(self, shifts):
        """Compute payroll results for all shifts.

        Args:
            shifts: List of Shift objects.

        Returns:
            List of dicts with keys: employee_id, week_start,
            reg, daily_ot, weekly_ot, gross.
        """
        # Group shifts by employee and week
        by_emp_week = defaultdict(list)
        for shift in shifts:
            key = (shift.employee_id, shift.week_start)
            by_emp_week[key].append(shift)

        results = []
        for (emp_id, week_start), week_shifts in by_emp_week.items():
            total_hours = sum(s.rounded_duration for s in week_shifts)

            # Compute overtime using weekly threshold only
            reg = round(total_hours, 2)
            daily_ot = 0.0
            weekly_ot = 0.0

            if reg > WEEKLY_THRESHOLD:
                weekly_ot = round(reg - WEEKLY_THRESHOLD, 2)
                reg = WEEKLY_THRESHOLD

            # Compute gross pay
            gross = round(
                reg * REGULAR_RATE
                + daily_ot * OVERTIME_RATE
                + weekly_ot * DOUBLE_TIME_RATE,
                2
            )

            results.append({
                'employee_id': emp_id,
                'week_start': week_start,
                'reg': reg,
                'daily_ot': daily_ot,
                'weekly_ot': weekly_ot,
                'gross': gross,
            })

        # Sort by week start date, then employee ID
        results.sort(key=lambda r: (r['week_start'], r['employee_id']))

        return results


class ReportFormatter:
    """Formats payroll results for output.

    Generates the detailed payroll report and optional
    summary line. Output uses comma delimiters.
    """

    HEADER = "Employee,Week,Regular,OT,Weekly_OT,Pay"
    DELIMITER = ","

    def format(self, results):
        """Format results into the output report.

        Args:
            results: List of result dicts from PayrollEngine.

        Returns:
            Formatted output string.
        """
        lines = [self.HEADER]

        for r in results:
            week_str = r['week_start'].strftime('%Y-%m-%d')
            parts = [
                r['employee_id'],
                week_str,
                str(r['reg']),
                str(r['daily_ot']),
                str(r['weekly_ot']),
                f"{r['gross']:.2f}",
            ]
            lines.append(self.DELIMITER.join(parts))

        # Use CRLF line endings for cross-platform compatibility
        output = '\r\n'.join(lines) + '\r\n'
        return output

    def format_summary(self, results):
        """Format a one-line summary of payroll totals.

        Args:
            results: List of result dicts from PayrollEngine.

        Returns:
            Summary string, or empty string if no results.
        """
        if not results:
            return ""

        total_employees = len(set(r['employee_id'] for r in results))
        total_reg = sum(r['reg'] for r in results)
        total_ot = sum(r['daily_ot'] + r['weekly_ot'] for r in results)
        total_pay = sum(r['gross'] for r in results)

        return (f"TOTAL: {total_employees} employees, "
                f"{total_reg:.2f} regular hours, "
                f"{total_ot:.2f} overtime hours, "
                f"${total_pay:.2f} total pay")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert timesheet CSV to payroll report'
    )
    parser.add_argument(
        'input_file',
        help='Path to timesheet CSV file'
    )
    parser.add_argument(
        '--summary', action='store_true',
        help='Print summary totals after the report'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Print detailed processing information to stderr'
    )
    return parser.parse_args()


def main():
    """Main entry point for the converter."""
    args = parse_args()

    # Read input file
    reader = TimesheetReader(args.input_file)
    entries = reader.read()

    # Match entries into shifts
    matcher = ShiftMatcher()
    shifts = matcher.match(entries, verbose=args.verbose)

    # Verbose output: print each shift being processed
    if args.verbose:
        for shift in shifts:
            cin = shift.clock_in.strftime(TS_FORMAT)
            cout = shift.clock_out.strftime(TS_FORMAT)
            print(f"Processing shift: {shift.employee_id} {cin} - {cout}",
                  file=sys.stderr)

    # Compute payroll
    engine = PayrollEngine()
    results = engine.compute(shifts)

    # Format and write report
    formatter = ReportFormatter()
    output = formatter.format(results)
    sys.stdout.write(output)

    # Optional summary line
    if args.summary:
        summary = formatter.format_summary(results)
        if summary:
            print(summary)

    # Successful completion
    sys.exit(0)


if __name__ == '__main__':
    main()
