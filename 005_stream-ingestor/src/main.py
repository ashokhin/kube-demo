"""
stream-ingestor entry point.

Runs Spark Structured Streaming that:
  1. Reads JSON records from Kafka topic `risk-results`
     (published by risk-engine after each async calculation)
  2. Writes raw records as Parquet to HDFS (partitioned by dt=YYYY-MM-DD)
  3. Aggregates per (dt, modelVersion) and inserts into Hive risk.risk_aggregates

A background Prometheus HTTP server exposes /metrics on :9090.

KRB5 ticket is obtained by the init container before this process starts.
The ticket path is passed via KRB5CCNAME env var.
"""
import logging
import os
import sys

from prometheus_client import start_http_server

from src.config import settings
from src.stream_runner import run_streaming

logging.basicConfig(
    level=settings.log_level.upper(),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not settings.hdfs_mock_mode:
        os.environ.setdefault("KRB5CCNAME", settings.krb5ccname)

    start_http_server(settings.metrics_port)
    logger.info("Prometheus metrics server started port=%d", settings.metrics_port)

    logger.info(
        "Starting stream-ingestor kafka_mock=%s hdfs_mock=%s hive_mock=%s kafka=%s topic=%s",
        settings.kafka_mock_mode,
        settings.hdfs_mock_mode,
        settings.hive_mock_mode,
        settings.kafka_bootstrap_servers,
        settings.kafka_topic_risk_results,
    )
    run_streaming(mock_mode=settings.kafka_mock_mode)


if __name__ == "__main__":
    main()
