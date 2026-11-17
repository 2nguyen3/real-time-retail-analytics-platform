-- Raw format keeps malformed JSON visible; no ignore-parse-errors switch is used.
CREATE TEMPORARY VIEW parsed_lines AS
SELECT payload, kafka_partition, kafka_offset, kafka_timestamp, event_ts, proc_time,
  JSON_VALUE(payload, '$.schema_version') AS schema_version,
  JSON_VALUE(payload, '$.transaction_id') AS transaction_id,
  JSON_VALUE(payload, '$.basket_id') AS basket_id,
  JSON_VALUE(payload, '$.product_id') AS product_id,
  JSON_VALUE(payload, '$.customer_id') AS customer_id,
  JSON_VALUE(payload, '$.store_id') AS store_id,
  JSON_VALUE(payload, '$.category_id') AS category_id,
  JSON_VALUE(payload, '$.quantity') AS quantity_text,
  JSON_VALUE(payload, '$.price') AS price_text,
  JSON_VALUE(payload, '$.line_revenue') AS revenue_text,
  JSON_VALUE(payload, '$.event_time') AS event_time_text,
  JSON_VALUE(payload, '$.emitted_at') AS emitted_at_text,
  JSON_VALUE(payload, '$.run_id') AS run_id,
  JSON_VALUE(payload, '$.source_type') AS source_type,
  JSON_VALUE(payload, '$.source_dataset') AS source_dataset,
  JSON_VALUE(payload, '$.event_time_basis') AS event_time_basis,
  JSON_VALUE(payload, '$.currency') AS currency
FROM kafka_lines;

CREATE TEMPORARY VIEW typed_lines AS
SELECT *,
  TRY_CAST(quantity_text AS INT) AS quantity,
  TRY_CAST(price_text AS DECIMAL(18, 8)) AS price,
  TRY_CAST(revenue_text AS DECIMAL(18, 2)) AS line_revenue
FROM parsed_lines;

CREATE TEMPORARY VIEW classified_lines AS
SELECT *, CASE
  WHEN payload IS NOT JSON OBJECT THEN 'invalid_json'
  WHEN schema_version IS NULL OR schema_version <> '1.0.0' THEN 'schema_version'
  WHEN transaction_id IS NULL OR TRIM(transaction_id) = '' THEN 'transaction_id'
  WHEN run_id IS NULL OR TRIM(run_id) = '' THEN 'run_id'
  WHEN store_id IS NULL OR TRIM(store_id) = '' THEN 'store_id'
  WHEN product_id IS NULL OR TRIM(product_id) = '' THEN 'product_id'
  WHEN source_dataset IS NULL OR TRIM(source_dataset) = '' THEN 'source_dataset'
  WHEN source_type IS NULL OR source_type NOT IN ('original', 'transformed', 'synthetic') THEN 'source_type'
  WHEN event_time_basis IS NULL OR event_time_basis NOT IN
       ('source_utc', 'assumed_timezone', 'synthetic') THEN 'event_time_basis'
  WHEN source_type = 'synthetic' AND event_time_basis <> 'synthetic' THEN 'time_provenance'
  WHEN currency IS NULL OR NOT REGEXP(currency, '^[A-Z]{3}$') THEN 'currency'
  WHEN quantity IS NULL OR quantity <= 0 OR quantity > 100000 THEN 'quantity'
  WHEN price_text IS NULL OR NOT REGEXP(price_text, '^(0|[1-9][0-9]{0,9})\.[0-9]{8}$')
       OR price IS NULL OR price < 0 THEN 'price'
  WHEN revenue_text IS NULL OR NOT REGEXP(revenue_text, '^(0|[1-9][0-9]{0,11})\.[0-9]{2}$')
       OR line_revenue IS NULL OR line_revenue < 0 THEN 'line_revenue'
  WHEN event_time_text IS NULL OR NOT REGEXP(event_time_text,
       '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
       OR event_ts IS NULL
       OR DATE_FORMAT(event_ts, 'yyyy-MM-dd''T''HH:mm:ss''Z''') <> event_time_text THEN 'event_time'
  WHEN ROUND(price * quantity, 2) <> line_revenue THEN 'revenue_mismatch'
  ELSE 'valid' END AS quality_status
FROM typed_lines;

CREATE TEMPORARY VIEW valid_lines AS
SELECT * FROM classified_lines WHERE quality_status = 'valid';

-- First arrival wins. State TTL is configured by run_sql.py for unbounded jobs.
CREATE TEMPORARY VIEW deduplicated_lines AS
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY run_id, transaction_id ORDER BY proc_time ASC) AS row_num
  FROM valid_lines
) WHERE row_num = 1;
