-- Primary keys already cover lookups by run/store and run/store/product.
CREATE INDEX IF NOT EXISTS idx_sales_store_product_run_product
  ON sales_by_store_product (run_id, product_id);
CREATE INDEX IF NOT EXISTS idx_sales_store_minute_run_time
  ON sales_by_store_minute (run_id, window_start);
