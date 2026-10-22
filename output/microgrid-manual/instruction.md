# Day-Ahead Demand Forecast — St. Magnus Island Microgrid

You are the grid operator for St. Magnus Island, a small North Atlantic
community (~3,000 residents) with a diesel-battery microgrid. You have
10 weeks of hourly demand and weather data (Oct 6 – Dec 14, 2025) and need
a day-ahead dispatch forecast for the coming weeks.

Your task is to improve `/app/forecast.py` so it produces accurate hourly
demand forecasts for any requested period.

## What to do

Run:

```
python3 /app/forecast.py --start 2025-12-15 --weeks 3
```

This must write `/app/forecast.csv` with the day-ahead hourly demand
forecast.

## Data files

All data is in `/app/data/`. **Read `/app/data/README.md`** for timezone
conventions, DST handling, and which demand file is authoritative.
**Read `/app/operators_notes.md`** for how the island's demand behaves.

Files available:

| File | Period | Description |
|------|--------|-------------|
| `meter_export.csv` | Oct 6 – Dec 14, 2025 | Hourly demand (MW) — see README for authoritative source |
| `demand_cleaned.csv` | Oct 6 – Dec 14, 2025 | Smoothed version — see README before using |
| `weather.csv` | Sep 29, 2025 – Jan 4, 2026 | Hourly temperature (°C), covers forecast period |
| `calendar.csv` | Sep 29, 2025 – Jan 4, 2026 | Daily `holiday` and `ferry_day` flags |

## Output specification

`/app/forecast.csv` must have:

- Exactly two columns: `timestamp` (string) and `demand` (float)
- Timestamp format: `YYYY-MM-DD HH:MM:SS` in Europe/London local time
- Exactly 168 × N rows (N = `--weeks` argument)
- Sequential hourly timestamps from the start date 00:00:00 — no gaps, no duplicates
- All demand values finite and positive (MW)

## CLI interface

```
python3 /app/forecast.py --start YYYY-MM-DD --weeks N
```

Both flags are required. The script must work for any valid start date
and positive integer week count.

## Accuracy target

Day-ahead MAPE below 9 % on unseen weeks, including the kinds of days the
operator's notes describe. The forecast weeks are winter weeks: expect
weather and calendar conditions that the training weeks only partly
cover.

## Runtime

The forecast must complete in under 60 seconds.

## Public validation

A test suite in `/app/tests_public/` checks output format and MAPE on an
ordinary validation week (Sep 29 – Oct 5). Run:

```
python3 -m pytest /app/tests_public/
```

This covers common-path correctness only.
