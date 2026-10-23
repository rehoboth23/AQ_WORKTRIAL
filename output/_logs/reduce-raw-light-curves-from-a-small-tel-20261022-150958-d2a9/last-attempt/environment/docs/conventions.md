# Observatory Reduction Conventions v3.2

## §1 Time System

The observatory uses Heliocentric Julian Date (HJD). Convert from JD to HJD using the following formula:

```
HJD = JD + (X·cos(α)cos(δ) + Y·sin(α)cos(δ) + Z·sin(δ)) / 173.144632
```

where α (right ascension) and δ (declination) are the star's coordinates from the catalogue (in radians), and X, Y, Z are the Sun's geocentric equatorial rectangular coordinates in AU, computed as:

```
n = JD - 2451545.0
g = radians(357.529 + 0.98560028·n)
L = radians(280.459 + 0.98564736·n)
λ = L + radians(1.915)·sin(g)
ε = radians(23.439 - 0.00000036·n)
R = 1.00014 - 0.01672·cos(g)
X = R·cos(λ)
Y = R·cos(ε)·sin(λ)
Z = R·sin(ε)·sin(λ)
```

## §2 Comparison Star Vetting

A comparison star is valid only if it passes **both** of the following checks:

1. **Saturation**: Reject any comparison star whose flux exceeds 50,000 ADU in **any single observation**.
2. **Variability**: Reject any comparison star whose instrumental-magnitude scatter σ(m_inst) exceeds 0.03 mag across nights, where m_inst = −2.5·log₁₀(flux).

Among the remaining valid comparison stars, select the one with the lowest `catalog_mag` (brightest).

A target for which no valid comparison star exists cannot be calibrated. Report `period_days = NA`, `amplitude_mag = NA`, `mean_mag = NA` for such targets.

## §3 Magnitude Calibration

For each target star with a valid comparison star:

1. Compute instrumental magnitudes: `m_inst = −2.5·log₁₀(flux)`
2. Compute the differential magnitude: `Δm = m_inst(target) − m_inst(comp)`
3. Apply the airmass correction: `Δm_corr = Δm − k·(X_target − X_comp)`, where `k = 0.15` mag/airmass and `X_target`, `X_comp` are the airmass values from the observation data
4. Compute the calibrated magnitude: `m_cal = Δm_corr + m_cat_comp`

where `m_cat_comp` is the catalogue magnitude of the selected comparison star.

The mean magnitude (`mean_mag`) is the arithmetic mean of all calibrated magnitudes for that target.

## §4 Period Analysis

If fewer than 3 nights of observations are available for a target star, do not attempt period search. Report `period_days = NA`. Amplitude also cannot be computed without a period; report `amplitude_mag = NA`. Mean magnitude is still computed if a valid comparison star exists.

For targets with 3 or more nights:

1. Convert all JD timestamps to HJD (§1).
2. Run a Lomb-Scargle periodogram over the period range **[0.1, 50.0] days**. Use at least **10× oversampling** relative to the natural frequency resolution (1/T, where T is the total baseline span of that star's observations).
3. Identify the best peak (highest power) and its period `P_best`.
4. **Alias rejection** — Compute the 1-day alias periods:

   ```
   P_alias = 1 / |1/P_best ± 1|
   ```

   Compute both the `+1` and `−1` variants. Only consider aliases that fall within the search range [0.1, 50.0] days.

5. If any alias period has periodogram power greater than **50%** of the best peak's power:
   - Phase-fold the data at `P_best` and at each qualifying alias period.
   - Fit a 3-harmonic Fourier model (§5) to each phase-folded light curve.
   - Compute the reduced chi-squared for each fit:

     ```
     χ²_red = (1 / (N − p)) · Σᵢ ((m_obs,i − m_model(φᵢ)) / σᵢ)²
     ```

     where N is the number of observations, `p = 7` (model parameters), and `σᵢ` is the calibrated magnitude error propagated from the `flux_err` column: `σ_m = 1.0857·σ_flux/flux`; `σ_m_cal = √(σ_m,target² + σ_m,comp²)`.
   - Select the period with the **lowest** reduced chi-squared.
6. The selected period is the final period estimate.

## §5 Amplitude

The 3-harmonic Fourier model is:

```
m(φ) = a₀ + a₁·sin(2πφ) + b₁·cos(2πφ) + a₂·sin(4πφ) + b₂·cos(4πφ) + a₃·sin(6πφ) + b₃·cos(6πφ)
```

fitted to the phase-folded calibrated magnitudes (weighted least squares using the calibrated magnitude errors), where the phase is `φ = (HJD / P) mod 1`.

`amplitude_mag` = ½ × (max(m(φ)) − min(m(φ)))

where the model is evaluated at **100 evenly-spaced phases**: φ = 0, 0.01, 0.02, …, 0.99.

If no period estimate is available (fewer than 3 nights or no valid comparison star), `amplitude_mag = NA`.

## §6 Catalogue

The field catalogue (`catalogue.csv`) is read-only and authoritative. Do not modify it under any circumstances.
