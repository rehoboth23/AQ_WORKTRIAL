# Address Normalisation Engine: Archived Log

`addresses.tsv` holds about 900 before/after pairs taken from the log of the
retired municipal address-normalisation engine.  Each line is one address:
the raw input, a tab, then the engine's output.  The file is UTF-8 with Unix
line endings and has no header.

The engine's rule list was not archived.  These pairs are the only record of
what it did; new addresses will be judged against the same engine.

Output lines never carry leading or trailing whitespace.  An input line that
is empty, or contains only whitespace, produces an empty output line.
