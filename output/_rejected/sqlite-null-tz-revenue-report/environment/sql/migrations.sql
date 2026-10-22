-- PostgreSQL to SQLite Migration Notes (SQL)
-- This file documents SQL-level changes made during the migration.
-- It is kept for reference and does not need to be executed.

-- Note: PostgreSQL's AT TIME ZONE syntax is not available in SQLite.
-- To convert UTC timestamps to a local timezone, use the modifier syntax:
--   date(timestamp_column, '+N hours') or date(timestamp_column, '-N hours')
-- The specific offset should match the business timezone.

-- PostgreSQL: SELECT created_at AT TIME ZONE 'America/New_York'
-- SQLite:     SELECT date(created_at, '-5 hours')  -- for EST (UTC-5)

-- Note: PostgreSQL's COALESCE works identically in SQLite
-- but NULL handling in aggregates may differ slightly in edge cases.
-- SUM(column) in both databases returns NULL if all values are NULL.
-- The behavior is actually the same, but be aware of NULL propagation
-- through computed columns and cascading views.

-- PostgreSQL allows creating indexes on expressions:
-- CREATE INDEX idx_tx_date ON transactions (date(created_at));
-- SQLite also supports this:
-- CREATE INDEX idx_tx_date ON transactions (date(created_at));

-- PostgreSQL uses ::type for casting, SQLite uses CAST(x AS type):
-- PostgreSQL: SELECT created_at::date
-- SQLite:     SELECT date(created_at)

-- PostgreSQL BOOLEAN values are true/false; SQLite uses 1/0:
-- PostgreSQL: WHERE include_in_revenue = true
-- SQLite:     WHERE include_in_revenue = 1

-- PostgreSQL EXTRACT(month FROM created_at)
-- SQLite strftime('%m', created_at)
