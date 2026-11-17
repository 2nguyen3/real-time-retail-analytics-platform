-- Offset boundaries and group ID are rendered by run_sql.py.
CREATE TEMPORARY TABLE kafka_lines (
  payload STRING,
  kafka_partition INT METADATA FROM 'partition' VIRTUAL,
  kafka_offset BIGINT METADATA FROM 'offset' VIRTUAL,
  kafka_timestamp TIMESTAMP_LTZ(3) METADATA FROM 'timestamp' VIRTUAL,
  event_ts AS TO_TIMESTAMP_LTZ(
    JSON_VALUE(payload, '$.event_time'),
    'yyyy-MM-dd''T''HH:mm:ss''Z''', 'UTC'),
  proc_time AS PROCTIME(),
  WATERMARK FOR event_ts AS event_ts - INTERVAL '5' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'retail.sales.transactions',
  'properties.bootstrap.servers' = 'kafka:9092',
  'properties.group.id' = '{{GROUP_ID}}',
  'format' = 'raw',
  'scan.startup.mode' = 'specific-offsets',
  'scan.startup.specific-offsets' = '{{START_OFFSETS}}'{{BOUND_OPTIONS}}
);
