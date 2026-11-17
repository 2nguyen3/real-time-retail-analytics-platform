BEGIN;

CREATE TABLE IF NOT EXISTS stores (
  store_id TEXT PRIMARY KEY,
  store_region TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
  product_id TEXT PRIMARY KEY,
  category_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL CHECK (source_type IN ('synthetic', 'transformed', 'original', 'mixed')),
  status TEXT NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'RUNNING', 'VALIDATED', 'FAILED')),
  producer_started_at TIMESTAMPTZ,
  flink_job_id TEXT,
  validated_at TIMESTAMPTZ,
  expected_records BIGINT CHECK (expected_records >= 0),
  observed_records BIGINT CHECK (observed_records >= 0),
  note TEXT
);

CREATE TABLE IF NOT EXISTS sales_by_store (
  run_id TEXT NOT NULL,
  store_id TEXT NOT NULL,
  currency VARCHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  transaction_count BIGINT NOT NULL CHECK (transaction_count >= 0),
  total_quantity BIGINT NOT NULL CHECK (total_quantity >= 0),
  total_revenue NUMERIC(28,2) NOT NULL CHECK (total_revenue >= 0),
  PRIMARY KEY (run_id, store_id, currency)
);

CREATE TABLE IF NOT EXISTS sales_by_store_product (
  run_id TEXT NOT NULL,
  store_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  currency VARCHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  transaction_count BIGINT NOT NULL CHECK (transaction_count >= 0),
  total_quantity BIGINT NOT NULL CHECK (total_quantity >= 0),
  total_revenue NUMERIC(28,2) NOT NULL CHECK (total_revenue >= 0),
  PRIMARY KEY (run_id, store_id, product_id, currency)
);

CREATE TABLE IF NOT EXISTS sales_by_store_minute (
  run_id TEXT NOT NULL,
  store_id TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  currency VARCHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  transaction_count BIGINT NOT NULL CHECK (transaction_count >= 0),
  total_quantity BIGINT NOT NULL CHECK (total_quantity >= 0),
  total_revenue NUMERIC(28,2) NOT NULL CHECK (total_revenue >= 0),
  CHECK (window_end = window_start + INTERVAL '1 minute'),
  PRIMARY KEY (run_id, store_id, window_start, currency)
);

COMMIT;
