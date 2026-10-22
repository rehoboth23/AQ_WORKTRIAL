-- queries.sql: Report queries for the daily summary
-- Only completed orders are included; cancelled orders are excluded
-- from all totals and breakdowns.
SELECT * FROM orders WHERE status = 'completed';
