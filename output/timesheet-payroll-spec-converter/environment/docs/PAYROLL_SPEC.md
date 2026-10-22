# Payroll Conversion Specification

## Overview

This document defines the rules for converting employee timesheet data into payroll reports. The converter reads a CSV of clock-in and clock-out records and produces a pipe-delimited payroll report. All implementations must follow these rules precisely. Where a rule differs from default programming behavior (such as Python's rounding), the difference is noted explicitly.

---

## Time Zone

All timestamps in the input CSV are expressed in the **America/Chicago** time zone. The converter must interpret every timestamp as being in America/Chicago and must perform all date and time calculations — day boundaries, week boundaries, date formatting — in this time zone. Do not treat naive timestamps as UTC or as the system local time. This matters because a timestamp near midnight Chicago may fall on a different calendar day in UTC, which would produce incorrect day and week assignments.

---

## Work Week Definition

A work week runs from **Monday 00:00:00 through Sunday 23:59:59** in the America/Chicago time zone. The "week start" for reporting is the Monday date of that work week, determined in the America/Chicago time zone.

### Cross-Week Shift Splitting

When a single shift spans a week boundary — that is, it starts before Monday 00:00 Chicago and ends on or after Monday 00:00 Chicago — the shift must be **split at the boundary**. The portion before the boundary belongs to the earlier week; the portion from the boundary onward belongs to the new week. Each portion is rounded to the nearest quarter-hour independently (see Rounding below).

A shift that starts exactly at Monday 00:00 Chicago is not split. A shift that ends exactly at Monday 00:00 Chicago is not split. Only a shift that *crosses* the boundary is split.

---

## Rounding

### Quarter-Hour Rounding

All shift durations are rounded to the nearest **quarter-hour (0.25 hours)** before any further calculation. This rounding is applied to each shift (or shift portion, after any cross-week splitting) before overtime is computed.

### Round-Half-Up

Rounding uses the **round-half-up** method: when a value is exactly halfway between two rounding increments, it rounds upward (toward the larger increment). **Python's built-in `round()` function uses banker's rounding (round-half-to-even) and must not be used for any rounding in this converter.** For example:

- 0.125 hours is exactly halfway between 0.00 and 0.25. Under round-half-up it rounds to 0.25. Under banker's rounding, `round(0.125, 2)` returns 0.12.
- 228.125 dollars is exactly halfway between 228.12 and 228.13. Under round-half-up it rounds to 228.13. Under banker's rounding it rounds to 228.12.

The round-half-up rule applies to **both** quarter-hour rounding of hours **and** cent-level rounding of monetary values (gross pay).

### Minimum Shift Duration

A shift whose quarter-hour-rounded duration is **less than 0.25 hours** is discarded entirely — it does not appear in any output and does not count toward overtime thresholds. A shift that rounds to exactly 0.25 hours is the minimum and is counted. This minimum exists because shifts under 15 minutes are considered de minimis and not compensable.

---

## Overtime

### Daily Overtime

For each calendar day (in America/Chicago), if an employee's total rounded hours from all shifts on that day exceed **8.00 hours**, the first 8.00 hours are classified as regular and the remainder is classified as daily overtime. Daily overtime is computed **per calendar day across all of an employee's shifts on that day**, not per individual shift.

For example, if an employee works two shifts of 5 hours each on the same day, the total is 10 hours for that day, resulting in 8.00 regular and 2.00 daily overtime. Computing per-shift (5 reg + 0 OT for each) would be incorrect.

### Weekly Overtime

After separating daily overtime, sum the remaining regular hours across all days in the work week. If the total regular hours exceed **40.00 hours**, the excess is reclassified as weekly overtime. **Daily overtime hours are never reclassified as weekly overtime.** Only regular hours in excess of 40.00 become weekly overtime.

For example: an employee works 9 hours each day Monday through Friday. Each day produces 8.00 regular + 1.00 daily OT. Total regular across the week = 40.00. Since 40.00 does not exceed 40.00, there is 0 weekly overtime. The final result is 40.00 regular, 5.00 daily OT, 0.00 weekly OT.

If the same employee also works 1 hour on Saturday (no daily OT on that day), total regular becomes 41.00. Now 1.00 hour is reclassified as weekly overtime. The result is 40.00 regular, 5.00 daily OT, 1.00 weekly OT.

---

## Duplicate and Incomplete Entries

### Duplicate Clock-In

If multiple entries have the **same employee ID and the same clock-in timestamp** (matching to the second), only the **first** such entry in file order is kept; the rest are discarded. This prevents a double clock-in from creating a phantom shift.

### Duplicate Clock-Out

If multiple entries have the **same employee ID and the same clock-out timestamp** (matching to the second), only the **last** such entry in file order is kept; the rest are discarded. This handles the case where an employee clocks out, then a supervisor corrects the time — the correction (later in the file) takes precedence.

After removing duplicates by these rules, the remaining entries for each employee are processed as shifts in file order.

### Missing Clock-Out

An entry with a clock-in but no clock-out (empty or absent field) cannot form a valid shift and is omitted from output. The converter must print a warning to stderr in exactly this format:

```
WARNING: incomplete shift for <employee_id> on <YYYY-MM-DD>
```

where `<employee_id>` is the entry's employee ID and `<YYYY-MM-DD>` is the clock-in date in America/Chicago. This warning does not affect the exit code.

---

## Output Format

### Delimiter and Header

Output is **pipe-delimited** using the `|` character. The first row is a header with these exact column names:

```
Employee ID|Week Start|Reg|Daily OT|Weekly OT|Gross
```

Note the specific column names: "Employee ID" with a space, "Daily OT" with a space, and "Weekly OT" with a space. These names must appear exactly as shown.

### Week Start Format

The Week Start column is formatted as **MM/DD**, zero-padded, representing the Monday date of the work week in America/Chicago. Single-digit months and days are zero-padded. For example, January 6, 2025 is formatted as `01/06`, not `1/6` or `2025-01-06`.

### Hours Format

The Reg, Daily OT, and Weekly OT columns are each formatted as **N.NN** with exactly two decimal places. Whole-number hours must still show `.00`. For example, 8 hours displays as `8.00`, not `8.0` or `8`.

### Gross Pay Format

Gross pay is formatted as **$N,NNN.NN**: a dollar sign prefix, a comma as the thousands separator for values of $1,000.00 or more, and exactly two decimal places. There is no space between the dollar sign and the number. Values under $1,000.00 have no comma separator.

Examples:
- $975.00 — no comma (under $1,000)
- $1,000.00 — comma at exactly $1,000
- $12,500.00 — comma for thousands place

### Line Endings

Each output line ends with **LF** (`\n`) only. No carriage return (`\r`) characters appear in the output. This applies to both the main report and any summary line.

### Row Sorting

Rows are sorted by **Employee ID** ascending using string comparison (lexicographic, not numeric), then by **Week Start** ascending in chronological order. For example, employee ID "A100" sorts before "A20" because the character '1' comes before '2' in string comparison, even though 100 > 20 numerically.

### Empty Weeks

If an employee has no hours in a particular work week (either no shifts or all shifts were discarded), no row is produced for that employee-week combination. Only weeks with positive hours appear in the output.

---

## Compensation

Pay rates are fixed as follows:

| Category | Rate | Multiplier |
|----------|------|------------|
| Regular | $25.00/hr | 1.0× |
| Daily Overtime | $37.50/hr | 1.5× |
| Weekly Overtime | $50.00/hr | 2.0× |

Gross pay for each employee-week is:

```
(regular_hours × $25.00) + (daily_ot_hours × $37.50) + (weekly_ot_hours × $50.00)
```

The result is **rounded to the nearest cent using round-half-up**, the same rounding rule described in the Rounding section, applied at the cent (0.01) level. Do not use Python's `round()` for this; it will produce incorrect results for values exactly halfway between cents.

---

## Exit Codes

The converter uses exit codes to signal outcome categories:

| Condition | Exit Code |
|-----------|-----------|
| At least one valid shift was processed | 0 |
| Input file cannot be opened (file not found or unreadable) | 1 |
| No valid shifts exist (all were discarded or incomplete) | 2 |

Warnings printed to stderr (such as incomplete shift warnings) do not affect the exit code. If at least one valid shift was processed alongside one or more warnings, the exit code is 0, not 2.

---

## Input Tolerance

### Blank Lines

Blank rows in the CSV input are silently skipped without error. A blank row is one where all fields are empty or contain only whitespace.

### Whitespace Trimming

Leading and trailing whitespace around field values in the CSV is trimmed before processing. For example, the employee ID `  E001  ` is processed as `E001`. This applies to all fields, including timestamps.
