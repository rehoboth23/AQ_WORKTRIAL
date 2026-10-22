#!/usr/bin/env python3
"""
Data generator for St. Magnus Island microgrid forecasting task.

Generates all CSV data files deterministically using a seeded simulator.
The same logic MUST be replicated in tests/simulator.py so that held-out
evaluation can regenerate training data and verify determinism.

All random numbers come from a single np.random.RandomState(42).
Order of RNG consumption:
  1. Temperature noise: rng.normal(0, 1.0, size=N)   N = total timestamps
  2. Demand noise:      rng.normal(0, 0.2, size=N)

The full timestamp series spans 2025-09-29 through 2026-01-04 (98 days)
in Europe/London local time.  On 2025-10-26 (BST->GMT fall-back) the
01:00 hour is duplicated, giving 2353 total timestamps (98*24 + 1).

Output files:
  /app/data/meter_export.csv              1681 rows (training period)
  /app/data/demand_cleaned.csv            1681 rows (5-h MA of meter_export)
  /app/data/weather.csv                   2353 rows (full period)
  /app/data/calendar.csv                    98 rows (daily, full period)
  /app/tests_public/validation_demand.csv  168 rows (Sep 29 - Oct 5)
"""

import os
import numpy as np
import pandas as pd

# == Constants ===============================================================

SEED = 42

FULL_START = pd.Timestamp(2025, 9, 29)
FULL_END   = pd.Timestamp(2026, 1, 4)

TRAIN_START = pd.Timestamp(2025, 10, 6)
TRAIN_END   = pd.Timestamp(2025, 12, 14)

VALID_START = pd.Timestamp(2025, 9, 29)
VALID_END   = pd.Timestamp(2025, 10, 5)

DST_DATE = pd.Timestamp(2025, 10, 26)

HEATING_THRESHOLD = 14.0   # deg C
HEATING_COEF      = 0.15   # MW per deg C below threshold
FERRY_BUMP        = 0.8    # MW
FERRY_START_HOUR  = 6
FERRY_END_HOUR    = 19     # inclusive -> hours 6-19 (06:00-20:00 window)
NOISE_SIGMA       = 0.2    # MW

HOLIDAY_FACTOR_REGULAR   = 0.70
HOLIDAY_FACTOR_LONG_WKND = 0.60

HOLIDAY_DATES = {
    pd.Timestamp(2025, 10, 31),   # Fri  - training
    pd.Timestamp(2025, 11, 1),    # Sat  - training (also ferry day)
    pd.Timestamp(2025, 11, 11),   # Tue  - training
    pd.Timestamp(2025, 12, 25),   # Thu  - held-out
    pd.Timestamp(2025, 12, 26),   # Fri  - held-out (long weekend)
    pd.Timestamp(2025, 12, 27),   # Sat  - held-out (also ferry day)
    pd.Timestamp(2026, 1, 1),     # Thu  - held-out
}

# == Base demand profiles (MW, 24 hourly values) =============================

WEEKDAY_PROFILE = np.array([
    3.5, 3.2, 3.0, 2.9, 3.1, 3.8,
    5.0, 6.5, 6.8, 6.0, 5.5, 5.3,
    5.5, 5.3, 5.2, 5.3, 5.5, 6.0,
    6.8, 6.5, 5.8, 5.0, 4.3, 3.8,
])  # mean ~ 5.0 MW

SATURDAY_PROFILE = np.array([
    3.2, 3.0, 2.8, 2.7, 2.8, 3.1,
    3.7, 4.4, 4.7, 4.5, 4.4, 4.3,
    4.5, 4.4, 4.3, 4.3, 4.4, 4.7,
    5.2, 5.0, 4.5, 4.0, 3.5, 3.3,
])  # mean ~ 4.0 MW

SUNDAY_PROFILE = np.array([
    3.0, 2.8, 2.7, 2.6, 2.7, 2.9,
    3.3, 3.7, 4.0, 3.9, 3.8, 3.7,
    3.9, 3.8, 3.7, 3.7, 3.8, 4.1,
    4.5, 4.3, 3.9, 3.5, 3.2, 3.1,
])  # mean ~ 3.5 MW (~ 70 % of weekday)

# == Calendar helpers ========================================================

def is_holiday(date):
    """True if *date* is a public holiday on St. Magnus."""
    return pd.Timestamp(date) in HOLIDAY_DATES

def is_ferry_day(date):
    """True if *date* is a scheduled ferry sailing day.

    Ferries run on the 1st and 3rd Saturday of each month, plus a
    special Winter Market sailing on Dec 27.
    """
    date = pd.Timestamp(date)
    if date.weekday() != 5:          # not Saturday
        return False
    dom = date.day
    if dom <= 7:                     # 1st Saturday
        return True
    if 15 <= dom <= 21:              # 3rd Saturday
        return True
    if date == pd.Timestamp(2025, 12, 27):
        return True
    return False

def holiday_factor(date):
    """Demand multiplier for a holiday (1.0 if not a holiday).

    Regular holiday (Tue/Wed/Thu/Sat/Sun): 0.70
    Friday or Monday holiday (long weekend): 0.60
    """
    if not is_holiday(date):
        return 1.0
    dow = pd.Timestamp(date).weekday()   # 0=Mon ... 6=Sun
    if dow in (0, 4):                    # Mon or Fri
        return HOLIDAY_FACTOR_LONG_WKND
    return HOLIDAY_FACTOR_REGULAR

# == Timestamp generation ====================================================

def generate_timestamps(start, end):
    """Hourly timestamps from *start* 00:00 through *end* 23:00.

    On 2025-10-26 the 01:00 hour is duplicated (BST->GMT fall-back).
    Returns a list of pandas Timestamps.
    """
    result = []
    day = start
    while day <= end:
        for h in range(24):
            ts = day + pd.Timedelta(hours=h)
            result.append(ts)
            if day.date() == DST_DATE.date() and h == 1:
                result.append(ts)       # duplicate 01:00
        day += pd.Timedelta(days=1)
    return result

# == Temperature model =======================================================

def generate_temperature(timestamps, rng):
    """Synthetic temperature (deg C) for each timestamp.

    Model:  seasonal linear trend  +  daily cosine cycle  +  Gaussian noise
            +  cold-snap and post-cold-snap modifiers.
    """
    n = len(timestamps)
    days = np.array([
        (ts.date() - pd.Timestamp(2025, 9, 1).date()).days
        for ts in timestamps
    ])
    hours = np.array([ts.hour for ts in timestamps])
    dates = [ts.date() for ts in timestamps]

    seasonal = 13.5 - 0.08 * days
    daily = 2.5 * np.cos(2 * np.pi * (hours - 15) / 24)
    noise = rng.normal(0, 1.0, size=n)

    temps = seasonal + daily + noise

    # Cold snap: Dec 22-24 (deep cold, below training minimum)
    cs_start = pd.Timestamp(2025, 12, 22).date()
    cs_end   = pd.Timestamp(2025, 12, 24).date()
    # Post-cold-snap chill: Dec 29 - Jan 4
    pcs_start = pd.Timestamp(2025, 12, 29).date()
    pcs_end   = pd.Timestamp(2026, 1, 4).date()

    for i, d in enumerate(dates):
        if cs_start <= d <= cs_end:
            temps[i] -= 8.0
        if pcs_start <= d <= pcs_end:
            temps[i] -= 2.0

    return np.round(temps, 2)

# == Demand model ============================================================

def generate_demand(timestamps, temps, rng):
    """Hourly demand (MW) for each timestamp."""
    n = len(timestamps)
    hours = np.array([ts.hour for ts in timestamps])
    dates = [ts.date() for ts in timestamps]

    demands = np.zeros(n)
    for i in range(n):
        d = pd.Timestamp(dates[i])
        h = int(hours[i])
        t = temps[i]

        # --- base profile ---
        if is_holiday(d):
            base = WEEKDAY_PROFILE[h] * holiday_factor(d)
        elif d.weekday() == 5:          # Saturday
            base = SATURDAY_PROFILE[h]
        elif d.weekday() == 6:          # Sunday
            base = SUNDAY_PROFILE[h]
        else:
            base = WEEKDAY_PROFILE[h]

        # --- heating load (linear, extrapolates below training range) ---
        heating = max(0.0, HEATING_THRESHOLD - t) * HEATING_COEF

        # --- ferry bump (additive on top of base, including holiday base) ---
        ferry = FERRY_BUMP if (is_ferry_day(d) and
                               FERRY_START_HOUR <= h <= FERRY_END_HOUR) else 0.0

        demands[i] = base + heating + ferry

    # --- Gaussian noise ---
    noise = rng.normal(0, NOISE_SIGMA, size=n)
    demands += noise
    demands = np.maximum(demands, 0.5)     # floor

    return np.round(demands, 4)

# == Main ====================================================================

def fmt_ts(ts):
    return ts.strftime('%Y-%m-%d %H:%M:%S')

def main():
    os.makedirs('/app/data', exist_ok=True)
    os.makedirs('/app/tests_public', exist_ok=True)

    rng = np.random.RandomState(SEED)

    # Full timestamp series
    all_ts = generate_timestamps(FULL_START, FULL_END)
    n = len(all_ts)
    assert n == 2353, f"Expected 2353 timestamps, got {n}"

    # Generate temperatures (consumes RNG: 2353 normal draws)
    all_temps = generate_temperature(all_ts, rng)

    # Generate demands (consumes RNG: 2353 more normal draws)
    all_demands = generate_demand(all_ts, all_temps, rng)

    # -- weather.csv (full period, with DST duplicate) --
    weather_df = pd.DataFrame({
        'timestamp': [fmt_ts(ts) for ts in all_ts],
        'temperature': all_temps,
    })
    weather_df.to_csv('/app/data/weather.csv', index=False)

    # -- meter_export.csv (training only, with DST duplicate) --
    ts_dates = np.array([ts.date() for ts in all_ts])
    train_mask = (ts_dates >= TRAIN_START.date()) & (ts_dates <= TRAIN_END.date())
    meter_df = pd.DataFrame({
        'timestamp': [fmt_ts(all_ts[i]) for i in range(n) if train_mask[i]],
        'demand': all_demands[train_mask],
    })
    meter_df.to_csv('/app/data/meter_export.csv', index=False)

    # -- demand_cleaned.csv (5-hour centered MA of meter_export) --
    cleaned_vals = pd.Series(meter_df['demand']).rolling(
        window=5, center=True, min_periods=1).mean()
    cleaned_vals = np.round(cleaned_vals.values, 4)
    cleaned_df = pd.DataFrame({
        'timestamp': meter_df['timestamp'],
        'demand': cleaned_vals,
    })
    cleaned_df.to_csv('/app/data/demand_cleaned.csv', index=False)

    # -- calendar.csv (daily, full period) --
    cal_rows = []
    day = FULL_START
    while day <= FULL_END:
        cal_rows.append({
            'date': day.strftime('%Y-%m-%d'),
            'holiday': int(is_holiday(day)),
            'ferry_day': int(is_ferry_day(day)),
        })
        day += pd.Timedelta(days=1)
    cal_df = pd.DataFrame(cal_rows)
    cal_df.to_csv('/app/data/calendar.csv', index=False)

    # -- validation_demand.csv (Sep 29 - Oct 5, ordinary week) --
    valid_mask = (ts_dates >= VALID_START.date()) & (ts_dates <= VALID_END.date())
    valid_df = pd.DataFrame({
        'timestamp': [fmt_ts(all_ts[i]) for i in range(n) if valid_mask[i]],
        'demand': all_demands[valid_mask],
    })
    valid_df.to_csv('/app/tests_public/validation_demand.csv', index=False)

    # Summary
    print(f"Weather:      {len(weather_df)} rows")
    print(f"Meter export: {len(meter_df)} rows")
    print(f"Cleaned:      {len(cleaned_df)} rows")
    print(f"Calendar:     {len(cal_df)} rows")
    print(f"Validation:   {len(valid_df)} rows")

if __name__ == '__main__':
    main()
