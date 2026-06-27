import asyncio
import logging
import logging.config
import signal

import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from src.config import settings
from src.metrics import metrics_response
import src.consumer as consumer

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

app = FastAPI(title="notification-service")


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/readyz")
async def readyz() -> JSONResponse:
    # The service is ready only when the RabbitMQ connection is established.
    # Kubernetes will not route traffic here until this returns 200.
    connected = consumer._connection is not None and not consumer._connection.is_closed
    if not connected:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="rabbitmq not connected")
    return JSONResponse({"status": "ok"})


@app.get("/metrics")
async def metrics() -> Response:
    return metrics_response()


async def main() -> None:
    await consumer.connect()

    loop = asyncio.get_running_loop()

    def _stop() -> None:
        logger.info("received stop signal, shutting down")
        # Schedule close() as a task — signal handlers must be synchronous,
        # but close() is a coroutine. create_task() bridges the gap.
        asyncio.create_task(consumer.close())

    # Register SIGTERM (Kubernetes pod termination) and SIGINT (Ctrl-C) handlers.
    # Both trigger a graceful shutdown: consumer stops after the current message,
    # RabbitMQ connection is closed, then uvicorn exits.
    loop.add_signal_handler(signal.SIGTERM, _stop)
    loop.add_signal_handler(signal.SIGINT, _stop)

    # log_config=None disables uvicorn's own logging setup so our JSON config wins.
    server_config = uvicorn.Config(app, host="0.0.0.0", port=settings.port, log_config=None)
    server = uvicorn.Server(server_config)

    # Run HTTP server and message consumer concurrently.
    # asyncio.gather() exits when both coroutines complete.
    await asyncio.gather(
        server.serve(),
        consumer.consume(),
    )
    logger.info("shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
