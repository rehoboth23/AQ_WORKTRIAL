# St. Magnus Island Microgrid — Data Documentation

## Overview

This directory contains hourly demand, weather, and calendar data for the
St. Magnus Island diesel-battery microgrid (population ~3,000, North
Atlantic).  Peak winter demand is around 8–9 MW; summer minimum around 2 MW.

## Files

| File | Rows | Period | Description |
|------|------|--------|-------------|
| `meter_export.csv` | 1681 | Oct 6 – Dec 14, 2025 | Authoritative hourly demand (MW) |
| `demand_cleaned.csv` | 1681 | Oct 6 – Dec 14, 2025 | 5-hour moving-average smoothed demand |
| `weather.csv` | 2353 | Sep 29, 2025 – Jan 4, 2026 | Hourly temperature (°C) |
| `calendar.csv` | 98 | Sep 29, 2025 – Jan 4, 2026 | Daily holiday and ferry_day flags |

## Timezone Convention

All timestamps are in **Europe/London local time** (BST during summer,
GMT during winter).  Timestamps are stored as naive strings in format
`YYYY-MM-DD HH:MM:SS`.

## DST Handling

On **2025-10-26**, clocks fall back from BST to GMT, creating a 25-hour
day with **duplicate timestamps at 01:00**.  Both `meter_export.csv` and
`weather.csv` contain this duplicate — the first occurrence is the BST
reading and the second is the GMT reading.

**Rule:** For duplicate hours, keep the **later** reading (the second
occurrence in the file).  In pandas:

```python
df = df.drop_duplicates(subset='timestamp', keep='last')
```

## Authoritative Source

**`meter_export.csv` is the authoritative source for demand data.**

`demand_cleaned.csv` is provided for convenience but smooths genuine
demand spikes (e.g., ferry-day load bumps, heating-load peaks) using a
5-hour centered moving average.  **Do not use `demand_cleaned.csv` for
model training** — it systematically underestimates peak loads and will
degrade forecast accuracy.

## Weather Data

`weather.csv` covers the full period (Sep 29, 2025 – Jan 4, 2026),
including the forecast period.  Temperature is in °C and follows the same
timezone and DST conventions as the demand data.  The same DST duplicate
at 01:00 on 2025-10-26 appears in this file.

## Calendar Data

`calendar.csv` contains daily flags (0 or 1):

- `holiday` — 1 on public holidays, 0 otherwise
- `ferry_day` — 1 on ferry sailing days, 0 otherwise

See `/app/operators_notes.md` for details on holiday effects and the
ferry schedule.
