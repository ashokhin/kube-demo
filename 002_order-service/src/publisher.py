import json
import logging
from typing import Any

import aio_pika

from src.config import settings
from src.metrics import ORDERS_EVENTS_PUBLISHED

logger = logging.getLogger(__name__)

# Module-level connection state. Initialized in connect(), closed in close().
# Using module globals instead of a class keeps the interface simple for this demo.
_connection: aio_pika.abc.AbstractConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect() -> None:
    global _connection, _channel, _exchange
    # connect_robust automatically reconnects on network failures.
    # This is important in Kubernetes where RabbitMQ may restart independently.
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    # TOPIC exchange routes messages by routing_key pattern (e.g. "order.*").
    # durable=True survives RabbitMQ restarts — the exchange is persisted to disk.
    _exchange = await _channel.declare_exchange(
        settings.orders_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    logger.info("connected to RabbitMQ", extra={"exchange": settings.orders_exchange})


async def close() -> None:
    if _connection:
        await _connection.close()


async def publish(event_type: str, payload: dict[str, Any]) -> None:
    assert _exchange is not None, "publisher not connected"
    message = aio_pika.Message(
        body=json.dumps({"event_type": event_type, "payload": payload}).encode(),
        content_type="application/json",
        # PERSISTENT: RabbitMQ writes the message to disk before acknowledging.
        # Without this, messages are lost if RabbitMQ crashes before delivery.
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    # routing_key equals event_type (e.g. "order.created").
    # Consumers bind their queues to the exchange with matching patterns.
    await _exchange.publish(message, routing_key=event_type)
    ORDERS_EVENTS_PUBLISHED.labels(event_type=event_type).inc()
    logger.info("event published", extra={"event_type": event_type})


async def check_connection() -> bool:
    return _connection is not None and not _connection.is_closed
