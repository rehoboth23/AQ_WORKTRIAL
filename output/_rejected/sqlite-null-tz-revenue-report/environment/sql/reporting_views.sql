-- Reporting views for monthly revenue calculation
-- These views aggregate from v_eligible_transactions through daily to monthly levels

DROP VIEW IF EXISTS v_monthly_summary;
DROP VIEW IF EXISTS v_daily_revenue;

-- v_daily_revenue: Aggregate eligible transactions by merchant and day
-- Revenue date is derived from the transaction creation timestamp
CREATE VIEW v_daily_revenue AS
SELECT
  t.merchant_id,
  date(t.created_at) as revenue_date,
  SUM(t.amount) as gross_revenue,
  SUM(t.refund_amount) as total_refunds,
  COUNT(*) as transaction_count
FROM v_eligible_transactions t
GROUP BY t.merchant_id, date(t.created_at);

-- v_monthly_summary: Aggregate daily revenue into monthly totals
CREATE VIEW v_monthly_summary AS
SELECT
  strftime('%Y-%m', dr.revenue_date) as month,
  dr.merchant_id,
  SUM(dr.gross_revenue) as gross_revenue,
  SUM(dr.total_refunds) as total_refunds,
  SUM(dr.gross_revenue) - SUM(dr.total_refunds) as net_revenue,
  SUM(dr.transaction_count) as transaction_count
FROM v_daily_revenue dr
GROUP BY strftime('%Y-%m', dr.revenue_date), dr.merchant_id;
