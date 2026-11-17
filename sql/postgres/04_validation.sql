\pset null '(null)'
\echo 'Schema and primary keys'
SELECT c.relname AS table_name, pg_get_constraintdef(k.oid) AS primary_key
FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
WHERE c.relname IN ('stores','products','pipeline_runs','sales_by_store',
                    'sales_by_store_product','sales_by_store_minute') AND k.contype = 'p'
ORDER BY c.relname;

\echo 'Revenue types and NOT NULL'
SELECT table_name, column_name, data_type, numeric_precision, numeric_scale, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name IN
  ('sales_by_store','sales_by_store_product','sales_by_store_minute')
  AND column_name IN ('total_revenue','run_id','currency')
ORDER BY table_name, column_name;

\echo 'Indexes (including primary-key indexes)'
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND tablename IN
  ('sales_by_store','sales_by_store_product','sales_by_store_minute')
ORDER BY tablename, indexname;

\echo 'Run summaries: each aggregate table is checked separately'
SELECT 'sales_by_store' AS table_name, currency, COUNT(*) AS rows,
  SUM(transaction_count) AS transaction_count, SUM(total_quantity) AS quantity,
  SUM(total_revenue) AS revenue
FROM sales_by_store WHERE run_id = :'run_id' GROUP BY currency
UNION ALL
SELECT 'sales_by_store_product', currency, COUNT(*), SUM(transaction_count),
  SUM(total_quantity), SUM(total_revenue)
FROM sales_by_store_product WHERE run_id = :'run_id' GROUP BY currency
UNION ALL
SELECT 'sales_by_store_minute', currency, COUNT(*), SUM(transaction_count),
  SUM(total_quantity), SUM(total_revenue)
FROM sales_by_store_minute WHERE run_id = :'run_id' GROUP BY currency
ORDER BY table_name, currency;

\echo 'Duplicate aggregate keys: expected all zero'
SELECT 'sales_by_store' AS table_name, COUNT(*) AS duplicate_groups FROM (
  SELECT run_id, store_id, currency FROM sales_by_store
  WHERE run_id = :'run_id' GROUP BY 1,2,3 HAVING COUNT(*) > 1
) x
UNION ALL
SELECT 'sales_by_store_product', COUNT(*) FROM (
  SELECT run_id, store_id, product_id, currency FROM sales_by_store_product
  WHERE run_id = :'run_id' GROUP BY 1,2,3,4 HAVING COUNT(*) > 1
) x
UNION ALL
SELECT 'sales_by_store_minute', COUNT(*) FROM (
  SELECT run_id, store_id, window_start, currency FROM sales_by_store_minute
  WHERE run_id = :'run_id' GROUP BY 1,2,3,4 HAVING COUNT(*) > 1
) x;

\echo 'Dimension gaps'
SELECT
  (SELECT COUNT(*) FROM sales_by_store s LEFT JOIN stores d USING (store_id)
   WHERE s.run_id = :'run_id' AND d.store_id IS NULL) AS missing_stores,
  (SELECT COUNT(*) FROM sales_by_store_product s LEFT JOIN products d USING (product_id)
   WHERE s.run_id = :'run_id' AND d.product_id IS NULL) AS missing_products;

\echo 'Report query plan by store'
EXPLAIN (ANALYZE, BUFFERS)
SELECT store_id, currency, total_revenue FROM sales_by_store
WHERE run_id = :'run_id' ORDER BY total_revenue DESC;

\echo 'Report query plan by minute range'
EXPLAIN (ANALYZE, BUFFERS)
SELECT window_start, store_id, currency, total_revenue
FROM sales_by_store_minute
WHERE run_id = :'run_id'
  AND window_start >= TIMESTAMPTZ '2024-01-01 00:00:00+00'
  AND window_start < TIMESTAMPTZ '2024-01-02 00:00:00+00'
ORDER BY window_start, store_id;
