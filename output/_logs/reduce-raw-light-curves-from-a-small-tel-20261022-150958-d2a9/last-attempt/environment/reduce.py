#!/usr/bin/env python3
"""Variable star light curve reducer.

Usage:
    python3 reduce.py NIGHTS_DIR

Reads catalogue.csv and night_*.csv from NIGHTS_DIR,
writes calibrated magnitudes and period estimates to /app/out/stars.csv.

Output columns: star_id, period_days, amplitude_mag, mean_mag
  period_days   — 6 significant figures or NA
  amplitude_mag — 3 decimal places or NA
  mean_mag      — 3 decimal places or NA
"""

import sys
import os
import csv
import math


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    nights_dir = sys.argv[1]
    output_dir = "/app/out"
    os.makedirs(output_dir, exist_ok=True)

    # ── Read catalogue ──────────────────────────────────────────────
    catalogue = []
    cat_path = os.path.join(nights_dir, "catalogue.csv")
    if os.path.exists(cat_path):
        with open(cat_path) as f:
            for row in csv.DictReader(f):
                catalogue.append(row)

    # ── Read night files ────────────────────────────────────────────
    observations = []
    if os.path.isdir(nights_dir):
        for fname in sorted(os.listdir(nights_dir)):
            if fname.startswith("night_") and fname.endswith(".csv"):
                with open(os.path.join(nights_dir, fname)) as f:
                    for row in csv.DictReader(f):
                        observations.append(row)

    # TODO: implement the full reduction pipeline per /app/docs/conventions.md
    #   §1  Convert JD → HJD
    #   §2  Vet comparison stars (saturation <50 000 ADU, σ(m_inst) <0.03 mag)
    #   §3  Differential photometry + airmass correction (k=0.15)
    #   §4  Lomb-Scargle [0.1–50 d], 10× oversampling, alias rejection
    #   §5  Amplitude from 3-harmonic model at 100 phases

    # ── Write output (placeholder) ──────────────────────────────────
    output_path = os.path.join(output_dir, "stars.csv")
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['star_id', 'period_days', 'amplitude_mag', 'mean_mag'])

    sys.exit(0)


if __name__ == '__main__':
    main()
