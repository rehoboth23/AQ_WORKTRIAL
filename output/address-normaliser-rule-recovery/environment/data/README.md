# Address Normalisation Style Guide

This document describes the conventions followed by the retired
municipal address-normalisation engine.  The ~900 before/after pairs
in `addresses.tsv` were produced by the same engine process that will
be used to evaluate new addresses.

## General Cleanup

- All output is **UPPERCASE**.
- Periods (`.`) are removed.
- Commas (`,`) are removed.
- Multiple whitespace characters are collapsed to a single space.
- Leading and trailing whitespace is stripped.

## Directional Prefixes

Directional abbreviations are **expanded** to their full words:

| Abbreviation | Full word   |
|-------------|-------------|
| N           | NORTH       |
| S           | SOUTH       |
| E           | EAST        |
| W           | WEST        |
| NE          | NORTHEAST   |
| NW          | NORTHWEST   |
| SE          | SOUTHEAST   |
| SW          | SOUTHWEST   |

Full direction words that already appear in the address (e.g. NORTH
as a street name) are **not** modified — the engine only expands
abbreviations, never contracts full words.

## Street Type Abbreviations

Street type abbreviations are expanded when they appear as the **last
element** of the street part — that is, at the end of the address or
immediately before a normalised unit designator (`#`, `ROOM`,
`BUILDING`, or `FLOOR`):

| Abbreviation | Full word  |
|-------------|------------|
| ST          | STREET     |
| AVE         | AVENUE     |
| RD          | ROAD       |
| DR          | DRIVE      |
| LN          | LANE       |
| BLVD        | BOULEVARD  |
| PL          | PLACE      |
| CT          | COURT      |

Street type abbreviations in other positions are **not** expanded.
For example, "ST" meaning "Saint" in a name like "ST ANDREWS" stays
unchanged.

## Unit Designators

| Input    | Output   |
|----------|----------|
| SUITE    | #        |
| STE      | #        |
| APT      | #        |
| UNIT     | #        |
| RM       | ROOM     |
| BLDG     | BUILDING |
| FL       | FLOOR    |

## PO Box Addresses

PO BOX normalisation applies to the **standard format with spaces**:

- `P O BOX` (with spaces between P, O, and BOX) is normalised to
  `PO BOX`.

The format `POBOX` (no space between PO and BOX) is **not**
normalised and remains unchanged.

## Rule Ordering

The engine applies rules in a specific order.  The same rules applied
in a different order may produce different results when rules overlap.
Key ordering dependencies:

- Period removal must occur **before** direction expansion so that
  period-containing abbreviations like `N.W.` are correctly recognised.
- Compound direction expansion (`NE` → `NORTHEAST`) must occur
  **before** single-letter expansion (`N` → `NORTH`).
- Unit designator normalisation (which produces `#`, `ROOM`,
  `BUILDING`, `FLOOR`) must occur **before** street type expansion so
  that the position-dependent lookahead can see the normalised unit
  designators.

## Rare Rules

Some rules fire only rarely (2–3 times in the training data).  These
include special handling of unit designators within PO Box addresses
and other uncommon patterns.

## Near-Miss Patterns

Some patterns that **look** normalisable are left unchanged by the
engine:

- Full direction words used as street names (e.g. "NORTH AVE" →
  "NORTH AVENUE", **not** "N AVENUE").
- Street type abbreviations in non-final positions (e.g. "ST
  ANDREWS" stays as "ST ANDREWS").
- "POBOX" without a space is not converted to "PO BOX".

## About the Training Data

The training pairs in `addresses.tsv` were produced by the same
process that will be used to generate test pairs.  The ~900 pairs
cover common patterns as well as rare rules and near-miss cases.
