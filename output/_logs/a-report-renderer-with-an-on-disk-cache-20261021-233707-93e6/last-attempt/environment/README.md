# ReportForge

Command-line tool for generating formatted HTML reports from CSV
transaction data.  Supports product-catalog lookups, multi-currency
conversion, and configurable formatting — with on-disk caching to speed
up repeated runs.

## Usage

```bash
python3 -m reportgen <report_type> --data <csv_path> --from <start> --to <end>
```

### Arguments

| Argument        | Description                                   |
|-----------------|-----------------------------------------------|
| `report_type`   | Template to use (e.g. `sales_report`)          |
| `--data PATH`   | Path to the CSV data file                      |
| `--from DATE`   | Start date, inclusive (`YYYY-MM-DD`)           |
| `--to DATE`     | End date, inclusive (`YYYY-MM-DD`)             |
| `--fresh`       | Force a fresh render, ignoring the cache       |

## Input Files

### Transaction Data (CSV)

| Column        | Description                          |
|---------------|--------------------------------------|
| `date`        | Transaction date (`YYYY-MM-DD`)      |
| `product_id`  | Product identifier (e.g. `P001`)     |
| `quantity`    | Number of units                      |
| `unit_price`  | Price per unit in local currency     |
| `currency`    | Currency code (`US`, `EU`, `UK`, …)  |

### Product Catalog — `/app/refdata/products.json`

Maps product IDs to display names:

```json
{ "P001": { "name": "Widget Alpha" } }
```

### Exchange Rates — `/app/refdata/rates.json`

Conversion factors to USD:

```json
{ "EU": { "to_usd": 1.10, "name": "Euro" } }
```

### Formatting — `/app/config/formatting.yml`

Controls report appearance:

```yaml
currency_symbol: "$"
decimal_places: 2
heading: "Sales Report"
```

### Optional Overrides — `/app/config/overrides.yml`

If present, any key here overrides the matching key in
`formatting.yml`.  The file does not exist by default; create it to
customise formatting without editing the base configuration.

```yaml
currency_symbol: "€"
```

## Caching

Rendered reports are cached under `/app/cache/` and are keyed on report
type, data file, and date range.  The cache tracks all files that
influence the output — templates, data, configuration, and reference
data — and is invalidated automatically when any dependency changes.

Use `--fresh` to bypass the cache for a single run.

## Output

The rendered HTML is written to stdout.
