import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.metrics import REQUEST_COUNT, REQUEST_DURATION

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: any) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Record metrics after the response is ready so status_code is known.
        REQUEST_COUNT.labels(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        ).inc()
        REQUEST_DURATION.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration)

        # Structured JSON log — one line per request, parseable by log aggregators
        # (Loki, Elasticsearch, CloudWatch). Fields are emitted as extra JSON keys
        # because the formatter in main.py uses %(message)s only for the message field;
        # extra keys are appended by log aggregator pipelines or a JSON formatter library.
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": round(duration, 4),
            },
        )
        return response
