The SQLite database at `/app/store.db` has been corrupted by a recent schema migration. A junior developer ran `/app/migrate_v2.sh` to add a `cost_price` column to the `products` table. The script completed without errors, but the product data is now wrong — inventory counts are suspiciously low and every product has an invalid `category_id` of 0.

Your job: diagnose exactly how the migration corrupted the data and fix it so all product values are correct.

**Requirements after the fix:**

- The `products` table must have columns in this exact order: `id`, `name`, `price`, `cost_price`, `stock`, `category_id`.
- `cost_price` is the new column and should be `0.0` for all existing products.
- Every `category_id` must reference a valid row in the `categories` table (no zeros).
- `stock` values must be correct positive integers matching the original data.

The migration script at `/app/migrate_v2.sh` is still present — inspect it to understand what went wrong. Do **not** re-run the migration script; it will make things worse.
