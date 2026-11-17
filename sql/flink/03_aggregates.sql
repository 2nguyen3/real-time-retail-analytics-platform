CREATE TEMPORARY VIEW totals_by_run AS
SELECT run_id, COUNT(*) AS transaction_count, SUM(quantity) AS total_quantity,
  SUM(line_revenue) AS total_revenue
FROM deduplicated_lines GROUP BY run_id;

CREATE TEMPORARY VIEW revenue_by_store AS
SELECT run_id, store_id, COUNT(*) AS transaction_count,
  SUM(quantity) AS total_quantity, SUM(line_revenue) AS total_revenue
FROM deduplicated_lines GROUP BY run_id, store_id;

CREATE TEMPORARY VIEW revenue_by_product AS
SELECT run_id, product_id, COUNT(*) AS transaction_count,
  SUM(quantity) AS total_quantity, SUM(line_revenue) AS total_revenue
FROM deduplicated_lines GROUP BY run_id, product_id;

CREATE TEMPORARY VIEW revenue_by_store_product AS
SELECT run_id, store_id, product_id, COUNT(*) AS transaction_count,
  SUM(quantity) AS total_quantity, SUM(line_revenue) AS total_revenue
FROM deduplicated_lines GROUP BY run_id, store_id, product_id;
