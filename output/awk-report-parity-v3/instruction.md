Finance operations produce the monthly branch report with a legacy awk script, `/app/legacy/branch_report.awk`, which ran under mawk 1.3.4 on the old reporting servers. The awk interpreter has been removed from the servers (it is not installed on this machine either), and the report has to keep coming out byte for byte the same.

Write a Python replacement, `/app/report.py`, run as

    python3 /app/report.py <transactions-file>

that writes exactly the same bytes to standard output, and exits with the same status, as the awk script did under that mawk build, for any input file with the same layout as `/app/data/transactions.csv`: the same columns and the same kinds of values, including the malformed and unusual lines that file contains. The report is compared byte for byte.

What you have:

- `/app/legacy/branch_report.awk`, the script.
- `/app/data/transactions.csv`, with `transactions.out` and `transactions.rc`: the report and exit status mawk produced for it.
- `/app/data/practice/`, 32 further input files, each with the `.out` and `.rc` that mawk produced.
- `/app/docs/mawk-manual.txt` and `mawk-version.txt`, the manual and version string of the exact build that produced those outputs.

Use only the Python standard library. Your script must not run awk or any other external program.

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
