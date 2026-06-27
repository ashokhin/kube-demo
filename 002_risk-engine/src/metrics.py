"""
Prometheus metrics for risk-engine.

Naming convention: <namespace>_<subsystem>_<name>_<unit>
Namespace: risk_engine

PromQL examples:
  # Calculation rate per model version (last 5 min)
  rate(risk_engine_calculations_total[5m])

  # 99th percentile calculation duration
  histogram_quantile(0.99, rate(risk_engine_calculation_duration_seconds_bucket[5m]))

  # Kafka consumer lag proxy: consumed vs errors
  rate(risk_engine_kafka_consumed_total[5m])
"""
from prometheus_client import Counter, Gauge, Histogram

CALCULATIONS_TOTAL = Counter(
    "risk_engine_calculations_total",
    "Total number of risk calculations",
    ["model_version", "status"],
)

CALCULATION_ERRORS = Counter(
    "risk_engine_calculation_errors_total",
    "Total number of failed risk calculations",
    ["model_version"],
)

CALCULATION_DURATION = Histogram(
    "risk_engine_calculation_duration_seconds",
    "Time spent on a full calculation pipeline (HDFS read + compute + Hive write)",
    ["model_version"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

KAFKA_CONSUMED_TOTAL = Counter(
    "risk_engine_kafka_consumed_total",
    "Total messages consumed from risk-jobs Kafka topic",
    ["status"],
)

KAFKA_CONSUMER_LAG = Gauge(
    "risk_engine_kafka_consumer_lag",
    "Estimated Kafka consumer lag (messages behind latest offset)",
)

ACTIVE_CALCULATIONS = Gauge(
    "risk_engine_active_calculations",
    "Number of risk calculations currently in progress",
)
