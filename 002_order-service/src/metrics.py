from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Labels ["method", "path", "status_code"] allow filtering by any combination:
#   rate(order_service_requests_total{status_code="500"}[5m])   — error rate
#   rate(order_service_requests_total{path="/orders"}[1m])      — endpoint throughput
# Avoid high-cardinality labels like user_id or order_id — each unique value
# creates a new time series in Prometheus, which can exhaust memory.
REQUEST_COUNT = Counter(
    "order_service_requests_total",
    "Total number of requests received",
    ["method", "path", "status_code"],
)

# Histogram buckets default to [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10].
# PromQL: histogram_quantile(0.95, rate(order_service_request_duration_seconds_bucket[5m]))
REQUEST_DURATION = Histogram(
    "order_service_request_duration_seconds",
    "Request duration in seconds",
    ["method", "path"],
)

# Business metric: tracks successful order creation regardless of HTTP layer.
# Use rate() in PromQL to compute orders per second:
#   rate(order_service_orders_created_total[1m])
ORDERS_CREATED = Counter(
    "order_service_orders_created_total",
    "Total number of orders created",
)

# Label ["event_type"] enables per-event-type filtering:
#   rate(order_service_events_published_total{event_type="order.created"}[5m])
# Alerts on this counter detect publisher failures independently of HTTP errors.
ORDERS_EVENTS_PUBLISHED = Counter(
    "order_service_events_published_total",
    "Total number of events published to RabbitMQ",
    ["event_type"],
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
