ReportForge generates formatted HTML reports from CSV transaction data. It caches rendered reports to speed up repeated runs. The cache is not working correctly: changing source files and re-running the same report command can still produce stale output.

**Goal:** The cache must be fixed so that re-running a report always produces output reflecting the current state of all files that affect it. The cache must still serve valid hits: identical inputs with no intervening changes should produce a cache hit, avoiding re-renders.

**Command:** `python3 -m reportgen <report_type> --data <csv_path> --from <start> --to <end>`

Output is printed to stdout as HTML.
