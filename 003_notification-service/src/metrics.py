from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Split received/processed/failed into separate counters so alerting rules
# can detect when processed < received (backlog) or failed > 0 independently.
MESSAGES_RECEIVED = Counter(
    "notification_service_messages_received_total",
    "Total number of messages received from RabbitMQ",
    ["event_type"],
)

MESSAGES_PROCESSED = Counter(
    "notification_service_messages_processed_total",
    "Total number of messages successfully processed",
    ["event_type"],
)

MESSAGES_FAILED = Counter(
    "notification_service_messages_failed_total",
    "Total number of messages that failed processing",
    ["event_type"],
)

# Histogram (not Gauge) because processing time is a distribution we want to
# query with percentiles (e.g. p99 via histogram_quantile in PromQL).
PROCESSING_DURATION = Histogram(
    "notification_service_processing_duration_seconds",
    "Message processing duration in seconds",
    ["event_type"],
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
