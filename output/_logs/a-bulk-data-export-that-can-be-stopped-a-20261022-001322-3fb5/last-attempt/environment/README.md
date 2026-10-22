# Warehouse Inventory Audit Export Tool

`audit_export.py` exports inventory transactions from a SQLite database
to a CSV file with running per-warehouse balances.

## Usage

```
python audit_export.py --output report.csv
python audit_export.py --output report.csv --checkpoint --limit 50
python audit_export.py --output report.csv --checkpoint --resume
```

### Options

| Flag           | Description                                    |
|----------------|------------------------------------------------|
| `--db PATH`    | SQLite database path (default: `/app/warehouse.db`) |
| `--output PATH`| **Required.** Output CSV path                  |
| `--checkpoint` | Save periodic checkpoints during the export    |
| `--resume`     | Resume from the last checkpoint                |
| `--limit N`    | Stop after N records (for testing)             |
| `--info`       | Print database info and exit                   |
| `--ckpt-info`  | Print checkpoint info and exit                 |
| `--validate`   | Validate database before exporting             |

`--resume` implies `--checkpoint`.

## Output Format

The CSV file contains:

1. **Header row**: `id,warehouse_id,tx_date,tx_type,quantity,balance,description`
2. **Data rows**: one per transaction, sorted by `(warehouse_id, tx_date, id)`.
   The `balance` column shows the warehouse's running balance *after*
   that transaction is applied (IN adds, OUT subtracts).
3. **Summary section**: a blank line, then a line starting with
   `# Summary`, followed by one line per warehouse in alphabetical
   order: `WAREHOUSE: final_balance`.

Example:

```
id,warehouse_id,tx_date,tx_type,quantity,balance,description
1,ALPHA,2024-01-02,IN,350,350,Received from supplier
2,ALPHA,2024-01-03,OUT,120,230,Shipped to customer
...

# Summary
ALPHA: 1250
BETA: 980
CENTRAL: 1100
DELTA: 750
GAMMA: 890
```

## Checkpoint / Resume

With `--checkpoint`, the tool saves progress to a checkpoint file
(`<output>.ckpt`) every *batch_size* records.  The batch size is
configured in `config.ini` (default: 25).

With `--resume`, the tool reads the checkpoint and continues the
export from where it left off.

**Invariant**: a resumed export must produce exactly the same output
as an uninterrupted run from the same database — same header, same
transaction rows in the same order with the same balance values, and
the same summary section.  This must hold regardless of when the
export is interrupted and resumed.

## Configuration

`config.ini` (located alongside the database):

```ini
[export]
batch_size = 25
```
