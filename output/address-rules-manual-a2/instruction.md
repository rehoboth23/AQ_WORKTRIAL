# Address Normaliser — Rule Recovery Task

A municipal government retired its address-normalisation engine. About 900 before/after address pairs from its log survive in `data/addresses.tsv`. Your task is to write a Python normaliser (`/app/normalise.py`) that reproduces the engine's behaviour on new addresses.

## Resources

- **Training data**: `data/addresses.tsv` — ~900 before/after pairs (tab-separated, one pair per line). The first column is the raw input; the second column is the engine's output.
- **Notes**: `data/README.md` — the format of the training file.
- **Public tests**: `tests_public/pairs.tsv` and `tests_public/run_tests.sh` — 60 simple test pairs you can use to check your progress. These cover common cases only.

## Interface Contract

`/app/normalise.py` must:

1. Read one address per line from **stdin** (default) or from a file specified by `--input FILE`.
2. Write one normalised address per line to **stdout** (default) or to a file specified by `--output FILE`.
3. Preserve the `--input` and `--output` CLI flags.
4. Produce one output line per input line. Empty input lines produce empty output lines.
5. Exit with code 0 on success.

## Accuracy Requirement

Your normaliser must reproduce the engine on at least **95%** of held-out address pairs produced by the same engine. It must not read the training data or any other data file at runtime.

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
