"""
Prometheus metrics for stream-ingestor.

Exposed on :9090/metrics via a background HTTP server (prometheus_client.start_http_server).
Spark driver does not run a web server by default, so we start our own.

PromQL examples:
  # Micro-batch throughput
  rate(stream_ingestor_records_processed_total[5m])

  # Micro-batch duration p99
  histogram_quantile(0.99, rate(stream_ingestor_batch_duration_seconds_bucket[5m]))

  # Failed batches
  rate(stream_ingestor_batch_failures_total[5m])
"""
from prometheus_client import Counter, Gauge, Histogram

RECORDS_PROCESSED = Counter(
    "stream_ingestor_records_processed_total",
    "Total Kafka records processed across all micro-batches",
)

BATCH_DURATION = Histogram(
    "stream_ingestor_batch_duration_seconds",
    "Time to process a single Spark Structured Streaming micro-batch",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

BATCH_FAILURES = Counter(
    "stream_ingestor_batch_failures_total",
    "Total micro-batches that failed to write to HDFS/Hive",
)

HDFS_WRITES = Counter(
    "stream_ingestor_hdfs_writes_total",
    "Total successful Parquet partition writes to HDFS",
    ["status"],
)

HIVE_WRITES = Counter(
    "stream_ingestor_hive_writes_total",
    "Total successful aggregation rows written to Hive",
    ["status"],
)

KAFKA_LAG = Gauge(
    "stream_ingestor_kafka_lag_records",
    "Estimated Kafka consumer lag in number of records",
)

LAST_BATCH_TIMESTAMP = Gauge(
    "stream_ingestor_last_batch_timestamp_seconds",
    "Unix timestamp of the last successfully completed micro-batch",
)
