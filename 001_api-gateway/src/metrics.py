from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Prometheus metric names must be unique across the process.
# The prefix "api_gateway_" scopes them to this service so they don't collide
# with metrics from other services when scraped into the same Prometheus instance.

# Counter: monotonically increasing. Never decreases, never resets (except process restart).
# Labels split the counter into separate time series per method/path/status_code combination.
REQUEST_COUNT = Counter(
    "api_gateway_requests_total",
    "Total number of requests received",
    ["method", "path", "status_code"],
)

# Histogram: records the distribution of observed values in configurable buckets.
# Used for latency because we care about percentiles (p50, p95, p99), not just averages.
REQUEST_DURATION = Histogram(
    "api_gateway_request_duration_seconds",
    "Request duration in seconds",
    ["method", "path"],
)

# Tracks calls to upstream services separately from inbound requests.
# Useful for diagnosing whether errors originate in this service or upstream.
UPSTREAM_REQUEST_COUNT = Counter(
    "api_gateway_upstream_requests_total",
    "Total number of upstream requests",
    ["service", "status_code"],
)


def metrics_response() -> Response:
    # generate_latest() serializes all registered metrics to Prometheus text format.
    # CONTENT_TYPE_LATEST tells Prometheus which exposition format version to expect.
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
