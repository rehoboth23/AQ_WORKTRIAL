# Variable Star Light Curve Reducer

The observatory's automated reduction pipeline is broken and the original author has left. You must write a working `reduce.py` that processes raw nightly observation CSVs into calibrated magnitudes and period estimates for each variable star.

## Interface

```
python3 /app/reduce.py NIGHTS_DIR
```

- `NIGHTS_DIR` is a directory containing `catalogue.csv` and one or more `night_*.csv` files.
- The program writes its output to `/app/out/stars.csv`.
- Exit status is 0 in all cases, including when some or all output values are NA.

## Output Format

A CSV file with header row `star_id,period_days,amplitude_mag,mean_mag` and one row per target star from the catalogue, sorted by `star_id` in lexicographic order.

- `period_days`: 6 significant figures (e.g., `0.770000`, `1.23457`, or `1.23457e+01`) or the literal string `NA`
- `amplitude_mag`: 3 decimal places (e.g., `0.300`) or `NA`
- `mean_mag`: 3 decimal places (e.g., `12.500`) or `NA`

## Contract

- One row per target star from the catalogue, sorted by `star_id`.
- Stars with fewer than 3 nights of data: `period_days = NA`, `amplitude_mag = NA`; `mean_mag` is still computed if a valid comparison star exists.
- Stars that cannot be calibrated: all three values are NA.
- Exit status is 0 in all cases.
- The field catalogue (`catalogue.csv`) must not be modified.
- Every step of the reduction follows `/app/docs/conventions.md` v3.2.

## Data

Practice data is in `/app/data/`:
- `catalogue.csv`: 8 comparison stars (C001–C008) and 12 target stars (V001–V012) with RA, Dec, and catalogue magnitudes.
- `night_001.csv` through `night_010.csv`: raw observations with columns `star_id, jd, flux, flux_err, airmass`.

## Verification

A public test script is available at `/app/tests_public/run_public_tests.py`. It checks basic pipeline correctness on two clean stars.

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
