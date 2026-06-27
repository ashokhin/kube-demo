import logging
import logging.config
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.config import settings
from src.metrics import ORDERS_CREATED, metrics_response
import src.publisher as publisher
import src.repository as repository

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Connect to RabbitMQ on startup. The DB connection pool is lazy — SQLAlchemy
    # opens connections on first use, so no explicit DB connect step is needed.
    await publisher.connect()
    logger.info("startup complete")
    yield
    # Close the RabbitMQ connection gracefully on shutdown (SIGTERM from Kubernetes).
    await publisher.close()
    logger.info("shutdown complete")


app = FastAPI(title="order-service", lifespan=lifespan)


class CreateOrderRequest(BaseModel):
    customer_id: str
    product_id: str
    quantity: int


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/readyz")
async def readyz() -> JSONResponse:
    # Check both dependencies: pod should not receive traffic if either is unavailable.
    # Kubernetes keeps the pod out of Service endpoints until this returns 200.
    db_ok = await repository.check_db_connection()
    mq_ok = await publisher.check_connection()
    if not db_ok or not mq_ok:
        raise HTTPException(status_code=503, detail={"db": db_ok, "rabbitmq": mq_ok})
    return JSONResponse({"status": "ok"})


@app.get("/metrics")
async def metrics() -> Response:
    return metrics_response()


@app.post("/orders", status_code=201)
async def create_order(req: CreateOrderRequest) -> JSONResponse:
    order = await repository.create_order(req.customer_id, req.product_id, req.quantity)
    # Publish the event after the DB commit so we never publish for an order
    # that failed to persist. The reverse order (publish then commit) risks
    # consumers processing an order that does not exist in the DB.
    await publisher.publish("order.created", {"order_id": order.id, "customer_id": order.customer_id})
    ORDERS_CREATED.inc()
    logger.info("order created", extra={"order_id": order.id})
    return JSONResponse({"id": order.id, "status": order.status}, status_code=201)


@app.get("/orders/{order_id}")
async def get_order(order_id: str) -> JSONResponse:
    order = await repository.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return JSONResponse({"id": order.id, "status": order.status, "customer_id": order.customer_id})
