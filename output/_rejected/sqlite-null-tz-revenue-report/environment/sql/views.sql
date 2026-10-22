-- Core views for the revenue analytics pipeline
-- Migrated from PostgreSQL to SQLite

DROP VIEW IF EXISTS v_merchant_region_summary;
DROP VIEW IF EXISTS v_eligible_transactions;

-- v_eligible_transactions: Filter to completed transactions that should be
-- included in revenue. Category rules determine inclusion: internal
-- transactions are excluded.
-- Note: In PostgreSQL, this used a LEFT JOIN with COALESCE on include_in_revenue.
CREATE VIEW v_eligible_transactions AS
SELECT t.id, t.merchant_id, t.amount, t.refund_amount, t.category, t.created_at
FROM transactions t
INNER JOIN category_rules cr ON t.category = cr.category
WHERE t.status = 'completed' AND cr.include_in_revenue = 1;

-- v_merchant_region_summary: Summary of merchant activity
-- (Used for regional analytics and dashboards)
CREATE VIEW v_merchant_region_summary AS
SELECT merchant_id, COUNT(*) as tx_count, SUM(amount) as total_amount
FROM transactions
WHERE status = 'completed'
GROUP BY merchant_id;
