"""
risk-engine entry point.

Starts a FastAPI HTTP server that exposes:
  POST /api/calculate  — synchronous risk calculation (REST path)
  GET  /healthz        — liveness probe
  GET  /readyz         — readiness probe
  GET  /metrics        — Prometheus metrics

Additionally starts a Kafka consumer thread (daemon) that:
  - Reads from topic `risk-jobs` (published by risk-ui /api/jobs/async)
  - Runs the same calculation pipeline as /api/calculate
  - Publishes results to topic `risk-results` (consumed by stream-ingestor)
"""
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from src.config import settings
from src.hdfs_client import HdfsClient
from src.hive_client import HiveClient
import src.kafka_consumer as kafka_consumer_module
from src.kafka_consumer import start_consumer
from src.metrics import (
    ACTIVE_CALCULATIONS,
    CALCULATION_DURATION,
    CALCULATION_ERRORS,
    CALCULATIONS_TOTAL,
)
from src import risk_calculator

logging.basicConfig(
    level=settings.log_level.upper(),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
    stream=sys.stdout,
)
# confluent-kafka logs via its own C-level callbacks, not Python logging.
logger = logging.getLogger(__name__)

app = FastAPI(title="risk-engine", version="0.1.0")

if not settings.hdfs_mock_mode:
    os.environ.setdefault("KRB5CCNAME", settings.krb5ccname)

hdfs = HdfsClient(settings.hdfs_url, mock_mode=settings.hdfs_mock_mode)
hive = HiveClient(settings.hive_host, settings.hive_port, settings.hive_database,
                  mock_mode=settings.hive_mock_mode)


class CalculationRequest(BaseModel):
    portfolioId: str
    modelVersion: str = "v1.0"
    scenario: str = "baseline"


@app.on_event("startup")
async def startup_event() -> None:
    # Start the Kafka consumer thread alongside the HTTP server.
    # daemon=True ensures it exits when the main process exits.
    start_consumer(hdfs, hive, risk_calculator, mock_mode=settings.kafka_mock_mode)
    logger.info("Kafka consumer thread started")


@app.post("/api/calculate")
async def calculate(request: CalculationRequest) -> dict:
    """
    Synchronous risk calculation pipeline (REST path):
      1. Read portfolio input data from HDFS
      2. Run risk model (VaR calculation)
      3. Write results to Hive (partitioned by date)
    """
    logger.debug(
        "SYNC calculate received portfolioId=%s modelVersion=%s scenario=%s",
        request.portfolioId, request.modelVersion, request.scenario,
    )
    ACTIVE_CALCULATIONS.inc()
    with CALCULATION_DURATION.labels(model_version=request.modelVersion).time():
        try:
            portfolio = hdfs.read_portfolio(
                request.portfolioId,
                settings.hdfs_input_path,
            )
            result = risk_calculator.calculate(portfolio, request.modelVersion)
            hive.write_risk_result(result)
            CALCULATIONS_TOTAL.labels(model_version=request.modelVersion, status="success").inc()
            return result
        except Exception as exc:
            CALCULATION_ERRORS.labels(model_version=request.modelVersion).inc()
            logger.error("Calculation failed portfolio_id=%s error=%s",
                         request.portfolioId, str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            ACTIVE_CALCULATIONS.dec()


@app.get("/healthz")
async def liveness() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readiness() -> Response:
    if not settings.kafka_mock_mode and not kafka_consumer_module.kafka_connected:
        return Response(
            content='{"status": "not ready", "reason": "kafka disconnected"}',
            status_code=503,
            media_type="application/json",
        )
    return Response(content='{"status": "ok"}', status_code=200, media_type="application/json")


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=False)
