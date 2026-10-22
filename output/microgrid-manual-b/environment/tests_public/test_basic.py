"""Public tests for the demand forecasting task.

Run:  python3 -m pytest /app/tests_public/

These tests check the common-path output contract and basic accuracy
on one held-out ordinary week (Sep 29 - Oct 5).  They cover roughly
30 % of what the hidden evaluation checks.
"""

import os
import subprocess

import numpy as np
import pandas as pd

FORECAST_SCRIPT = '/app/forecast.py'
OUTPUT_FILE = '/app/forecast.csv'
VALIDATION_FILE = '/app/tests_public/validation_demand.csv'


def run_forecast(start, weeks):
    """Run forecast.py and return the output DataFrame."""
    subprocess.run(
        ['python3', FORECAST_SCRIPT, '--start', start, '--weeks', str(weeks)],
        check=True, timeout=60,
    )
    return pd.read_csv(OUTPUT_FILE)


def test_forecast_exists():
    """forecast.csv exists after running forecast.py."""
    df = run_forecast('2025-09-29', 1)
    assert os.path.exists(OUTPUT_FILE)


def test_csv_format():
    """CSV has correct columns and row count."""
    df = run_forecast('2025-09-29', 1)
    assert list(df.columns) == ['timestamp', 'demand'], \
        f"Expected ['timestamp','demand'], got {list(df.columns)}"
    assert len(df) == 168, f"Expected 168 rows, got {len(df)}"


def test_timestamps_hourly():
    """Timestamps are sequential hourly with no gaps."""
    df = run_forecast('2025-09-29', 1)
    ts = pd.to_datetime(df['timestamp'])
    assert ts.iloc[0] == pd.Timestamp('2025-09-29 00:00:00')
    assert ts.iloc[-1] == pd.Timestamp('2025-10-05 23:00:00')
    diffs = ts.diff().dropna()
    assert (diffs == pd.Timedelta(hours=1)).all(), \
        "Timestamps are not sequential hourly"


def test_values_positive():
    """All demand values are positive and finite."""
    df = run_forecast('2025-09-29', 1)
    assert df['demand'].notna().all(), "NaN values found"
    assert (df['demand'] > 0).all(), "Non-positive demand values found"
    assert np.all(np.isfinite(df['demand'].values)), "Non-finite values found"


def test_cli_generic():
    """Script works with different start/weeks."""
    df = run_forecast('2025-12-15', 3)
    assert len(df) == 504, f"Expected 504 rows for 3-week forecast, got {len(df)}"
    ts = pd.to_datetime(df['timestamp'])
    assert ts.iloc[0] == pd.Timestamp('2025-12-15 00:00:00')
    assert ts.iloc[-1] == pd.Timestamp('2026-01-04 23:00:00')


def test_mape_validation():
    """MAPE on validation week (Sep 29 - Oct 5) is below 15 %."""
    df = run_forecast('2025-09-29', 1)
    truth = pd.read_csv(VALIDATION_FILE)

    # Align on timestamp
    df_ts = df['timestamp'].values
    truth_ts = truth['timestamp'].values
    assert len(df) == len(truth), \
        f"Row count mismatch: forecast {len(df)} vs truth {len(truth)}"

    forecast = df['demand'].values.astype(float)
    actual = truth['demand'].values.astype(float)

    mape = np.mean(np.abs((actual - forecast) / actual)) * 100
    assert mape < 15, \
        f'MAPE {mape:.2f}% exceeds 15% threshold'
