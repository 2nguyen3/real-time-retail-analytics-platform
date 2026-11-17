-- Runtime-only placeholders are filled by run_jdbc.py; never commit rendered SQL.
CREATE TEMPORARY TABLE pg_sales_by_store (
  run_id STRING,
  store_id STRING,
  currency STRING,
  transaction_count BIGINT,
  total_quantity BIGINT,
  total_revenue DECIMAL(28, 2),
  PRIMARY KEY (run_id, store_id, currency) NOT ENFORCED
) WITH (
  'connector' = 'jdbc',
  'url' = 'jdbc:postgresql://postgres:5432/retail_analytics',
  'table-name' = 'sales_by_store',
  'driver' = 'org.postgresql.Driver',
  'username' = '{{JDBC_USER}}',
  'password' = '{{JDBC_PASSWORD}}',
  'sink.buffer-flush.max-rows' = '100',
  'sink.buffer-flush.interval' = '1 s',
  'sink.max-retries' = '3',
  'sink.parallelism' = '1'
);

CREATE TEMPORARY TABLE pg_sales_by_store_product (
  run_id STRING,
  store_id STRING,
  product_id STRING,
  currency STRING,
  transaction_count BIGINT,
  total_quantity BIGINT,
  total_revenue DECIMAL(28, 2),
  PRIMARY KEY (run_id, store_id, product_id, currency) NOT ENFORCED
) WITH (
  'connector' = 'jdbc',
  'url' = 'jdbc:postgresql://postgres:5432/retail_analytics',
  'table-name' = 'sales_by_store_product',
  'driver' = 'org.postgresql.Driver',
  'username' = '{{JDBC_USER}}',
  'password' = '{{JDBC_PASSWORD}}',
  'sink.buffer-flush.max-rows' = '100',
  'sink.buffer-flush.interval' = '1 s',
  'sink.max-retries' = '3',
  'sink.parallelism' = '1'
);

CREATE TEMPORARY TABLE pg_sales_by_store_minute (
  run_id STRING,
  store_id STRING,
  window_start TIMESTAMP(3),
  window_end TIMESTAMP(3),
  currency STRING,
  transaction_count BIGINT,
  total_quantity BIGINT,
  total_revenue DECIMAL(28, 2),
  PRIMARY KEY (run_id, store_id, window_start, currency) NOT ENFORCED
) WITH (
  'connector' = 'jdbc',
  'url' = 'jdbc:postgresql://postgres:5432/retail_analytics',
  'table-name' = 'sales_by_store_minute',
  'driver' = 'org.postgresql.Driver',
  'username' = '{{JDBC_USER}}',
  'password' = '{{JDBC_PASSWORD}}',
  'sink.buffer-flush.max-rows' = '100',
  'sink.buffer-flush.interval' = '1 s',
  'sink.max-retries' = '3',
  'sink.parallelism' = '1'
);

-- Reuse Stage 05 Kafka parsing, validation, and (run_id, transaction_id) dedup.
-- Add currency to every grouping so unlike money units never mix.
CREATE TEMPORARY VIEW stage06_store AS
SELECT run_id, store_id, currency, COUNT(*) AS transaction_count,
  SUM(CAST(quantity AS BIGINT)) AS total_quantity,
  CAST(SUM(line_revenue) AS DECIMAL(28, 2)) AS total_revenue
FROM deduplicated_lines GROUP BY run_id, store_id, currency;

CREATE TEMPORARY VIEW stage06_store_product AS
SELECT run_id, store_id, product_id, currency, COUNT(*) AS transaction_count,
  SUM(CAST(quantity AS BIGINT)) AS total_quantity,
  CAST(SUM(line_revenue) AS DECIMAL(28, 2)) AS total_revenue
FROM deduplicated_lines GROUP BY run_id, store_id, product_id, currency;

CREATE TEMPORARY VIEW stage06_store_minute AS
SELECT run_id, store_id,
  CAST(window_start AS TIMESTAMP(3)) AS window_start,
  CAST(window_end AS TIMESTAMP(3)) AS window_end, currency,
  COUNT(*) AS transaction_count,
  SUM(CAST(quantity AS BIGINT)) AS total_quantity,
  CAST(SUM(line_revenue) AS DECIMAL(28, 2)) AS total_revenue
FROM TABLE(TUMBLE(TABLE deduplicated_lines, DESCRIPTOR(event_ts), INTERVAL '1' MINUTE))
GROUP BY run_id, store_id, window_start, window_end, currency;

EXECUTE STATEMENT SET
BEGIN
  INSERT INTO pg_sales_by_store SELECT * FROM stage06_store;
  INSERT INTO pg_sales_by_store_product SELECT * FROM stage06_store_product;
  INSERT INTO pg_sales_by_store_minute SELECT * FROM stage06_store_minute;
END;
