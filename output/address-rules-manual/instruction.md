# Address Normaliser — Rule Recovery Task

A municipal government retired its address-normalisation engine. About 900 before/after address pairs from its log survive in `data/addresses.tsv`. Your task is to write a Python normaliser (`/app/normalise.py`) that reproduces the engine's behaviour on new addresses.

## What You Know

- The engine applied about 25 ordered regex rewrite rules.
- Rule order matters when rules overlap — the same rules in a different order may produce different results.
- Some rules fire only rarely (2–3 times in the training data).
- Some patterns that look normalisable are left unchanged by the engine.

## Resources

- **Training data**: `data/addresses.tsv` — ~900 before/after pairs (tab-separated, one pair per line). The first column is the raw input; the second column is the engine's output.
- **Notes**: `data/README.md` — the format of the training file.
- **Public tests**: `tests_public/pairs.tsv` and `tests_public/run_tests.sh` — 60 simple test pairs you can use to check your progress. These only cover single-rule, straightforward cases.

## Interface Contract

`/app/normalise.py` must:

1. Read one address per line from **stdin** (default) or from a file specified by `--input FILE`.
2. Write one normalised address per line to **stdout** (default) or to a file specified by `--output FILE`.
3. Preserve the `--input` and `--output` CLI flags.
4. Produce one output line per input line. Empty input lines produce empty output lines.
5. Exit with code 0 on success.

## Accuracy Requirement

Your normaliser must reproduce the engine on at least **92%** of held-out address pairs. The held-out pairs are generated from the same process as the training data but with different random seeds, so they contain different addresses — a lookup table of training pairs will not help.

## Tips

- The training pairs cover both common and rare patterns. Pay special attention to pairs that appear only a few times.
- The order in which rules are applied matters. Examine training pairs where multiple rules interact.
- The public tests cover only simple single-rule cases. They will not catch ordering issues, rare rules, or near-miss patterns.
- Your normaliser must not depend on reading the training data file or any other data file at runtime. It must work purely from the rules it implements.
