-- One-minute event-time windows; event_ts comes from historical JSON event_time.
CREATE TEMPORARY VIEW revenue_by_store_minute AS
SELECT run_id, store_id, window_start, window_end,
  COUNT(*) AS transaction_count, SUM(quantity) AS total_quantity,
  SUM(line_revenue) AS total_revenue
FROM TABLE(TUMBLE(TABLE deduplicated_lines, DESCRIPTOR(event_ts), INTERVAL '1' MINUTE))
GROUP BY run_id, store_id, window_start, window_end;
