#!/usr/bin/env python3
"""Generate practice variable star observation data from seed 42.

Produces:
  catalogue.csv  — star_id, ra_deg, dec_deg, catalog_mag, star_type
  night_001.csv .. night_010.csv — star_id, jd, flux, flux_err, airmass

Usage:
  python3 generate_data.py [SEED] [OUTPUT_DIR]
  (defaults: seed=42, output_dir=/app/data)
"""

import sys
import os
import csv
import math
import numpy as np

# ── Physical constants ──────────────────────────────────────────────
K_EXT = 0.15            # extinction coefficient, mag/airmass
ZP = 2_000_000_000.0    # instrumental zero point, ADU
READ_NOISE = 25.0       # read-noise variance, ADU²

# ── Night JDs (spanning ~90 days, ~1-day spacing for aliasing) ─────
NIGHT_JDS = [
    2459000.5,          # night_001
    2459001.5,          # night_002
    2459002.5,          # night_003
    2459003.5,          # night_004
    2459005.5,          # night_005  (1-day gap)
    2459008.5,          # night_006  (2-day gap)
    2459015.5,          # night_007  (7-day gap)
    2459030.5,          # night_008  (15-day gap)
    2459060.5,          # night_009  (30-day gap)
    2459090.5,          # night_010  (30-day gap)
]

# ── Star definitions ────────────────────────────────────────────────
# Comparison stars: (id, ra, dec, cat_mag, saturated, variable,
#                    var_amp, var_period, var_phase)
#
# C006 is the brightest non-saturated comp but is intrinsically variable
# (σ(m_inst) ≈ 0.05 mag > 0.03 threshold).  catalog_mag=11.5 keeps its
# flux well below 50 000 ADU so it is NOT rejected by the saturation
# check — only the variability check catches it.
COMP_STARS = [
    ('C001', 120.00, 30.00, 12.5, False, False, 0.0, 0.0, 0.0),
    ('C002', 120.10, 30.10, 13.0, False, False, 0.0, 0.0, 0.0),
    ('C003', 120.20, 30.00, 13.5, False, False, 0.0, 0.0, 0.0),
    ('C004', 119.90, 30.20, 14.0, False, False, 0.0, 0.0, 0.0),
    ('C005', 120.30, 29.90, 14.5, False, False, 0.0, 0.0, 0.0),
    # C006: intrinsically variable (σ(m_inst) ≈ 0.05 mag > 0.03 threshold)
    # Brightest non-saturated comp, so it would be chosen if variability
    # check is skipped.
    ('C006', 120.10, 29.80, 11.5, False, True,  0.07, 3.0, 0.5),
    # C007: brightest (mag 10.5), flux > 50 000 ADU on good nights
    ('C007', 119.80, 30.10, 10.5, True,  False, 0.0, 0.0, 0.0),
    ('C008', 120.20, 30.20, 12.0, False, False, 0.0, 0.0, 0.0),
]

# Target stars: (id, ra, dec, mean_mag, period, amplitude,
#                phase_offset_radians, night_indices)
TARGET_STARS = [
    # near-alias (8 nights each)
    ('V001', 120.05, 30.05, 12.5, 0.77, 0.30, 0.0, [0,1,2,3,4,5,6,7]),
    ('V002', 120.15, 30.15, 13.0, 0.55, 0.25, 0.5, [0,1,2,3,4,5,6,7]),
    ('V003', 120.25, 30.05, 12.8, 0.91, 0.35, 1.0, [0,1,2,3,4,5,6,8]),
    # almost-exactly-1-day (8 nights each)
    ('V004', 119.95, 30.25, 13.2, 1.06, 0.28, 1.5, [0,1,2,3,4,5,6,9]),
    ('V005', 120.35, 29.95, 12.3, 1.10, 0.32, 2.0, [0,1,2,3,4,5,6,8]),
    ('V006', 120.15, 29.85, 13.5, 0.99, 0.20, 2.5, [0,1,2,3,4,5,6,9]),
    # clean, far from aliases
    ('V007', 120.05, 30.15, 12.0, 3.50, 0.40, 3.0, [0,1,2,3,4,5,6]),
    ('V008', 120.25, 30.15, 12.7, 5.20, 0.30, 0.0, [0,1,2,3,5,6,7]),
    ('V009', 119.85, 30.05, 13.8, 12.0, 0.45, 0.5, [0,1,2,3,4,5,6,7]),
    # sparse: <3 nights  (period must be NA; mean_mag still reported)
    ('V010', 120.35, 30.05, 12.4, 2.00, 0.25, 1.0, [0,7]),     # 30-day gap
    ('V011', 119.95, 29.95, 13.3, 4.00, 0.30, 1.5, [0,8]),     # 60-day gap
    ('V012', 120.05, 29.85, 12.9, 6.00, 0.22, 2.0, [0,9]),     # 90-day gap
]


def deg2rad(deg):
    return deg * math.pi / 180.0


def compute_hjd(jd, ra_rad, dec_rad):
    """JD → HJD using the heliocentric correction (conventions §1)."""
    n = jd - 2451545.0
    g = deg2rad(357.529 + 0.98560028 * n)
    L = deg2rad(280.459 + 0.98564736 * n)
    lam = L + deg2rad(1.915) * math.sin(g)
    eps = deg2rad(23.439 - 0.00000036 * n)
    R = 1.00014 - 0.01672 * math.cos(g)
    X_sun = R * math.cos(lam)
    Y_sun = R * math.cos(eps) * math.sin(lam)
    Z_sun = R * math.sin(eps) * math.sin(lam)
    corr = (X_sun * math.cos(ra_rad) * math.cos(dec_rad) +
            Y_sun * math.sin(ra_rad) * math.cos(dec_rad) +
            Z_sun * math.sin(dec_rad)) / 173.144632
    return jd + corr


def mag_to_flux(mag, airmass, transparency):
    """Apparent magnitude → expected flux (ADU)."""
    m_obs = mag + K_EXT * airmass
    return ZP * (10.0 ** (-0.4 * m_obs)) * transparency


def generate_field(seed, output_dir):
    rng = np.random.default_rng(seed)

    os.makedirs(output_dir, exist_ok=True)

    # ── Write catalogue ─────────────────────────────────────────────
    cat_path = os.path.join(output_dir, 'catalogue.csv')
    with open(cat_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['star_id', 'ra_deg', 'dec_deg', 'catalog_mag', 'star_type'])
        for cs in COMP_STARS:
            w.writerow([cs[0], f'{cs[1]:.6f}', f'{cs[2]:.6f}',
                        f'{cs[3]:.3f}', 'comp'])
        for ts in TARGET_STARS:
            w.writerow([ts[0], f'{ts[1]:.6f}', f'{ts[2]:.6f}',
                        f'{ts[3]:.3f}', 'target'])

    # ── Per-night observing conditions ──────────────────────────────
    night_cond = []
    for _ in NIGHT_JDS:
        night_cond.append({
            'transparency': 0.99 + 0.02 * rng.random(),   # 0.99 – 1.01
            'base_airmass': 1.15 + 0.20 * rng.random(),   # 1.15 – 1.35
        })

    # ── Write night files ───────────────────────────────────────────
    for ni, jd in enumerate(NIGHT_JDS):
        nc = night_cond[ni]
        t = nc['transparency']
        ba = nc['base_airmass']

        path = os.path.join(output_dir, f'night_{ni+1:03d}.csv')
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['star_id', 'jd', 'flux', 'flux_err', 'airmass'])

            # Comparison stars (observed every night)
            for cs in COMP_STARS:
                sid, ra_d, dec_d, cat_mag, is_sat, is_var, va, vp, vph = cs
                airmass = ba + 0.03 * (2.0 * rng.random() - 1.0)
                ra_r = deg2rad(ra_d)
                de_r = deg2rad(dec_d)
                hjd = compute_hjd(jd, ra_r, de_r)

                if is_var:
                    m_true = cat_mag + va * math.sin(2*math.pi * hjd / vp + vph)
                else:
                    m_true = cat_mag

                flux = mag_to_flux(m_true, airmass, t)
                ferr = math.sqrt(abs(flux) + READ_NOISE)
                fobs = flux + rng.normal(0.0, ferr)

                w.writerow([sid, f'{jd:.6f}', f'{fobs:.2f}',
                            f'{ferr:.2f}', f'{airmass:.4f}'])

            # Target stars (only on assigned nights)
            for ts in TARGET_STARS:
                sid, ra_d, dec_d, mmag, per, amp, ph_off, nights = ts
                if ni not in nights:
                    continue
                airmass = ba + 0.05 * (2.0 * rng.random() - 1.0)
                ra_r = deg2rad(ra_d)
                de_r = deg2rad(dec_d)
                hjd = compute_hjd(jd, ra_r, de_r)

                phase = 2.0 * math.pi * hjd / per + ph_off
                m_true = mmag + amp * math.sin(phase)

                flux = mag_to_flux(m_true, airmass, t)
                ferr = math.sqrt(abs(flux) + READ_NOISE)
                fobs = flux + rng.normal(0.0, ferr)

                w.writerow([sid, f'{jd:.6f}', f'{fobs:.2f}',
                            f'{ferr:.2f}', f'{airmass:.4f}'])


if __name__ == '__main__':
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    out = sys.argv[2] if len(sys.argv) > 2 else '/app/data'
    generate_field(seed, out)
