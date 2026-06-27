import logging
import logging.config
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse

from src.config import settings
from src.metrics import UPSTREAM_REQUEST_COUNT, metrics_response
from src.middleware import MetricsMiddleware

# Configure structured JSON logging before anything else so that even startup
# errors are captured in the same format as runtime logs.
# JSON output is required in Kubernetes: log aggregators (Loki, Fluentd) parse
# structured logs without extra configuration.
logging.config.dictConfig(
    {
        "version": 1,
        "formatters": {
            "json": {
                "()": "logging.Formatter",
                "fmt": '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
            }
        },
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
        "root": {"level": settings.log_level, "handlers": ["console"]},
    }
)

logger = logging.getLogger(__name__)

# Module-level variable holds the shared HTTP client instance.
# None until lifespan initializes it; the helper below guards against premature use.
_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # lifespan replaces the deprecated @app.on_event("startup"/"shutdown") hooks.
    # Everything before `yield` runs on startup; everything after runs on shutdown.
    # Using a single shared AsyncClient avoids opening a new TCP connection per request.
    global _http_client
    _http_client = httpx.AsyncClient(base_url=settings.order_service_url, timeout=10.0)
    logger.info("startup complete", extra={"order_service_url": settings.order_service_url})
    yield
    # Graceful shutdown: drain in-flight requests before closing the connection pool.
    await _http_client.aclose()
    logger.info("shutdown complete")


app = FastAPI(title="api-gateway", lifespan=lifespan)
app.add_middleware(MetricsMiddleware)


def http_client() -> httpx.AsyncClient:
    # Fail loudly if called before lifespan initializes the client.
    # This should never happen in production, but catches incorrect test setups early.
    assert _http_client is not None
    return _http_client


@app.get("/healthz")
async def healthz() -> JSONResponse:
    # Liveness probe: Kubernetes restarts the container if this fails.
    # Must NOT check external dependencies — only whether the process itself is alive.
    return JSONResponse({"status": "ok"})


@app.get("/readyz")
async def readyz() -> JSONResponse:
    # Readiness probe: Kubernetes removes the pod from Service endpoints while this fails.
    # We check order-service reachability — if it is down, we should not receive traffic.
    try:
        resp = await http_client().get("/healthz")
        resp.raise_for_status()
    except Exception:
        raise HTTPException(status_code=503, detail="order-service unreachable")
    return JSONResponse({"status": "ok"})


@app.get("/metrics")
async def metrics() -> Response:
    return metrics_response()


@app.post("/orders")
async def create_order(body: dict) -> JSONResponse:
    try:
        resp = await http_client().post("/orders", json=body)
        UPSTREAM_REQUEST_COUNT.labels(service="order-service", status_code=resp.status_code).inc()
        resp.raise_for_status()
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except httpx.HTTPStatusError as e:
        # Upstream returned 4xx/5xx — forward the status code to the caller.
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError:
        # Network-level failure (timeout, DNS, connection refused).
        raise HTTPException(status_code=503, detail="order-service unreachable")


@app.get("/orders/{order_id}")
async def get_order(order_id: str) -> JSONResponse:
    try:
        resp = await http_client().get(f"/orders/{order_id}")
        UPSTREAM_REQUEST_COUNT.labels(service="order-service", status_code=resp.status_code).inc()
        resp.raise_for_status()
        return JSONResponse(resp.json())
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="order-service unreachable")
