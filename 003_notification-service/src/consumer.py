import asyncio
import json
import logging

import aio_pika

from src.config import settings
from src.handlers import dispatch
from src.metrics import MESSAGES_RECEIVED

logger = logging.getLogger(__name__)

# Module-level connection shared between consume() and close().
_connection: aio_pika.abc.AbstractConnection | None = None
# asyncio.Event used as a cooperative shutdown flag.
# close() sets it; consume() checks it between messages to exit cleanly.
_should_stop = asyncio.Event()


async def connect() -> None:
    global _connection
    # connect_robust retries on network failures and reconnects automatically
    # after transient RabbitMQ outages — important in a Kubernetes environment.
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    logger.info("connected to RabbitMQ")


async def close() -> None:
    # Signal the consumer loop to stop after the current message finishes.
    _should_stop.set()
    if _connection:
        await _connection.close()


async def consume() -> None:
    assert _connection is not None
    channel = await _connection.channel()
    # prefetch_count=1: receive one message at a time.
    # The next message is not delivered until the current one is acked or nacked.
    # This prevents a single slow consumer from accumulating a backlog in memory.
    await channel.set_qos(prefetch_count=1)

    # durable=True: the queue survives RabbitMQ restarts.
    # Must match the declaration on the publisher side.
    queue = await channel.declare_queue(settings.queue_name, durable=True)

    logger.info("starting consumer", extra={"queue": settings.queue_name})

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            # Check the shutdown flag before processing each message.
            # This gives Kubernetes terminationGracePeriodSeconds to finish in-flight work.
            if _should_stop.is_set():
                break
            # message.process() is a context manager that acks on success and
            # nacks+requeues on exception (requeue=True).
            async with message.process(requeue=True):
                try:
                    body = json.loads(message.body)
                    event_type = body.get("event_type", "unknown")
                    payload = body.get("payload", {})
                    MESSAGES_RECEIVED.labels(event_type=event_type).inc()
                    await dispatch(event_type, payload)
                except json.JSONDecodeError:
                    logger.error("failed to decode message", extra={"body": message.body[:200]})
