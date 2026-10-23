#!/usr/bin/env python3
"""Public tests for the variable star reduction pipeline.

Generates two clean (non-alias) star fields from seeds 200 and 201,
runs reduce.py on each, and verifies:
  - period within 1% of the true period
  - mean_mag within 0.05 mag of the true mean

Usage:
    python3 /app/tests_public/run_public_tests.py
"""

import sys
import os
import csv
import math
import shutil
import tempfile
import subprocess

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required but not installed.")
    sys.exit(1)

# ── Constants (must match the conventions document) ─────────────────
K_EXT = 0.15
ZP = 2_000_000_000.0
READ_NOISE = 25.0


def deg2rad(deg):
    return deg * math.pi / 180.0


def compute_hjd(jd, ra_rad, dec_rad):
    """JD → HJD (conventions §1)."""
    n = jd - 2451545.0
    g = deg2rad(357.529 + 0.98560028 * n)
    L = deg2rad(280.459 + 0.98564736 * n)
    lam = L + deg2rad(1.915) * math.sin(g)
    eps = deg2rad(23.439 - 0.00000036 * n)
    R = 1.00014 - 0.01672 * math.cos(g)
    X = R * math.cos(lam)
    Y = R * math.cos(eps) * math.sin(lam)
    Z = R * math.sin(eps) * math.sin(lam)
    corr = (X * math.cos(ra_rad) * math.cos(dec_rad) +
            Y * math.sin(ra_rad) * math.cos(dec_rad) +
            Z * math.sin(dec_rad)) / 173.144632
    return jd + corr


def mag_to_flux(mag, airmass, transparency):
    m_obs = mag + K_EXT * airmass
    return ZP * (10.0 ** (-0.4 * m_obs)) * transparency


def _field_params(seed):
    """Return (period, mean_mag, amplitude, ra, dec) for the given seed."""
    if seed == 200:
        return 3.5, 12.5, 0.30, 120.0, 30.0
    elif seed == 201:
        return 7.2, 13.0, 0.35, 125.0, 25.0
    else:
        raise ValueError(f"No field params for seed {seed}")


def generate_clean_field(seed, output_dir):
    """Write catalogue.csv + night_001..006.csv for a clean single-target field."""
    rng = np.random.default_rng(seed)
    period, mean_mag, amplitude, ra, dec = _field_params(seed)

    # 3 stable, non-saturated comparison stars
    comps = [
        ('C001', ra + 0.10, dec + 0.10, 11.5),
        ('C002', ra - 0.10, dec + 0.10, 12.0),
        ('C003', ra + 0.10, dec - 0.10, 12.5),
    ]
    target = ('V001', ra, dec, mean_mag)

    # Night JDs: 2–5 day spacing (avoids 1-day aliasing)
    night_jds = [2459000.5, 2459002.5, 2459005.5,
                 2459009.5, 2459014.5, 2459020.5]

    os.makedirs(output_dir, exist_ok=True)

    # Catalogue
    with open(os.path.join(output_dir, 'catalogue.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['star_id', 'ra_deg', 'dec_deg', 'catalog_mag', 'star_type'])
        for c in comps:
            w.writerow([c[0], f'{c[1]:.6f}', f'{c[2]:.6f}', f'{c[3]:.3f}', 'comp'])
        w.writerow([target[0], f'{target[1]:.6f}', f'{target[2]:.6f}',
                    f'{target[3]:.3f}', 'target'])

    # Night files
    for ni, jd in enumerate(night_jds):
        transparency = 0.99 + 0.02 * rng.random()
        base_am = 1.15 + 0.20 * rng.random()

        with open(os.path.join(output_dir, f'night_{ni+1:03d}.csv'),
                  'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['star_id', 'jd', 'flux', 'flux_err', 'airmass'])

            for c in comps:
                sid, cra, cdec, cmag = c
                am = base_am + 0.03 * (2.0 * rng.random() - 1.0)
                m_obs = cmag + K_EXT * am
                flux = ZP * (10.0 ** (-0.4 * m_obs)) * transparency
                ferr = math.sqrt(abs(flux) + READ_NOISE)
                fobs = flux + rng.normal(0.0, ferr)
                w.writerow([sid, f'{jd:.6f}', f'{fobs:.2f}',
                            f'{ferr:.2f}', f'{am:.4f}'])

            sid, tra, tdec, tmag = target
            am = base_am + 0.05 * (2.0 * rng.random() - 1.0)
            hjd = compute_hjd(jd, deg2rad(tra), deg2rad(tdec))
            phase = 2.0 * math.pi * hjd / period
            m_true = tmag + amplitude * math.sin(phase)
            m_obs = m_true + K_EXT * am
            flux = ZP * (10.0 ** (-0.4 * m_obs)) * transparency
            ferr = math.sqrt(abs(flux) + READ_NOISE)
            fobs = flux + rng.normal(0.0, ferr)
            w.writerow([sid, f'{jd:.6f}', f'{fobs:.2f}',
                        f'{ferr:.2f}', f'{am:.4f}'])

    return {'period': period, 'mean_mag': mean_mag, 'amplitude': amplitude}


def run_single_test(seed):
    """Run reduce.py on a generated field and check the output."""
    tmp = tempfile.mkdtemp(prefix=f'pubtest_{seed}_')
    try:
        truth = generate_clean_field(seed, tmp)

        result = subprocess.run(
            ['python3', '/app/reduce.py', tmp],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            print(f'  FAIL: reduce.py exited with code {result.returncode}')
            if result.stderr:
                print(f'  stderr: {result.stderr[:300]}')
            return False

        out_path = '/app/out/stars.csv'
        if not os.path.exists(out_path):
            print('  FAIL: /app/out/stars.csv not produced')
            return False

        with open(out_path) as f:
            rows = list(csv.DictReader(f))

        if not rows:
            print('  FAIL: stars.csv has no data rows')
            return False

        row = None
        for r in rows:
            if r['star_id'] == 'V001':
                row = r
                break
        if row is None:
            print('  FAIL: V001 missing from output')
            return False

        ps = row['period_days']
        if ps == 'NA':
            print(f"  FAIL: period is NA (expected {truth['period']:.6f})")
            return False
        try:
            period = float(ps)
        except ValueError:
            print(f'  FAIL: period not parseable: {ps!r}')
            return False
        if abs(period - truth['period']) / truth['period'] > 0.01:
            print(f"  FAIL: period {period:.6f} not within 1% of "
                  f"{truth['period']:.6f}")
            return False

        ms = row['mean_mag']
        if ms == 'NA':
            print(f"  FAIL: mean_mag is NA (expected {truth['mean_mag']:.3f})")
            return False
        try:
            mean_mag = float(ms)
        except ValueError:
            print(f'  FAIL: mean_mag not parseable: {ms!r}')
            return False
        if abs(mean_mag - truth['mean_mag']) > 0.05:
            print(f"  FAIL: mean_mag {mean_mag:.3f} not within 0.05 of "
                  f"{truth['mean_mag']:.3f}")
            return False

        print(f"  PASS: period={period:.6f} (true={truth['period']:.6f}), "
              f"mean_mag={mean_mag:.3f} (true={truth['mean_mag']:.3f})")
        return True

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print('=' * 60)
    print('Public tests for variable star reduction pipeline')
    print('=' * 60)
    print()

    all_ok = True
    for seed in (200, 201):
        print(f'Seed {seed}:')
        if not run_single_test(seed):
            all_ok = False
        print()

    if all_ok:
        print('All public tests passed.')
        sys.exit(0)
    else:
        print('Some public tests FAILED.')
        sys.exit(1)


if __name__ == '__main__':
    main()
