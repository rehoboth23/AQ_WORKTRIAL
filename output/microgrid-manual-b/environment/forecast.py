#!/usr/bin/env python3
"""Day-ahead demand forecast for St. Magnus Island microgrid.

Starter implementation: naive last-week repeat.
Improve this to handle heating load, holiday effects, and ferry-day bumps.
See /app/data/README.md and /app/operators_notes.md for domain rules.
"""

import argparse
import pandas as pd
import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description='Day-ahead hourly demand forecast')
    parser.add_argument('--start', required=True,
                        help='Forecast start date (YYYY-MM-DD)')
    parser.add_argument('--weeks', type=int, required=True,
                        help='Number of weeks to forecast (>= 1)')
    args = parser.parse_args()

    start = pd.Timestamp(args.start)
    n_hours = args.weeks * 168

    # Load training data
    train = pd.read_csv('/app/data/meter_export.csv')
    train['timestamp'] = pd.to_datetime(train['timestamp'])

    # Naive forecast: repeat last 168 hours of training
    last_week = train.tail(168)['demand'].values

    # Build output
    timestamps = []
    demands = []
    for h in range(n_hours):
        ts = start + pd.Timedelta(hours=h)
        timestamps.append(ts.strftime('%Y-%m-%d %H:%M:%S'))
        demands.append(float(last_week[h % 168]))

    result = pd.DataFrame({
        'timestamp': timestamps,
        'demand': demands,
    })
    result.to_csv('/app/forecast.csv', index=False)
    print(f'Wrote {len(result)} rows to /app/forecast.csv')


if __name__ == '__main__':
    main()
