import logging
import os
from pathlib import Path
from typing import Any

import yaml

from src.metrics import MESSAGES_PROCESSED, MESSAGES_FAILED, PROCESSING_DURATION

logger = logging.getLogger(__name__)

# Path to the routing rules file. In Kubernetes this is a ConfigMap volume mount.
# Locally it falls back to the bundled src/handlers_config.yaml so the service
# works without Kubernetes (docker-compose, local dev).
_CONFIG_PATH = os.getenv(
    "HANDLERS_CONFIG_PATH",
    str(Path(__file__).parent / "handlers_config.yaml"),
)


def _load_routing_config(path: str) -> dict:
    # Load YAML routing rules at startup. The file is a ConfigMap mount in K8s —
    # updating the ConfigMap and restarting the pod is enough to change routing,
    # no image rebuild required.
    with open(path) as f:
        return yaml.safe_load(f)


_routing = _load_routing_config(_CONFIG_PATH)
logger.info("loaded handlers config", extra={"path": _CONFIG_PATH})


async def _dispatch_channels(
    event_type: str, channels: list[dict], payload: dict[str, Any]
) -> None:
    # Iterate channels defined in handlers_config.yaml for this event_type.
    # Each channel entry has `type`, `template`, and optional `retry`.
    for channel in channels:
        channel_type = channel.get("type", "log")
        template = channel.get("template", "")
        logger.info(
            "dispatching notification channel",
            extra={
                "event_type": event_type,
                "channel": channel_type,
                "template": template,
            },
        )
        # In a real service: call email/push/SMS gateway here based on channel_type.
        # Example: await email_client.send(template=template, payload=payload)


async def dispatch(event_type: str, payload: dict[str, Any]) -> None:
    handlers_map: dict = _routing.get("handlers", {})
    default_channels: list = _routing.get("default", [{"type": "log", "level": "warning"}])

    channels = handlers_map.get(event_type)
    if channels is None:
        # Event type not in routing config — use the default fallback.
        # Logged and discarded so unknown events do not block the queue.
        logger.warning("no handler for event, using default", extra={"event_type": event_type})
        channels = default_channels

    # Histogram.time() records wall-clock duration of all channels for this event.
    with PROCESSING_DURATION.labels(event_type=event_type).time():
        try:
            await _dispatch_channels(event_type, channels, payload)
            MESSAGES_PROCESSED.labels(event_type=event_type).inc()
        except Exception as exc:
            MESSAGES_FAILED.labels(event_type=event_type).inc()
            logger.error(
                "failed to process event",
                extra={"event_type": event_type, "error": str(exc)},
            )
            # Re-raise so message.process(requeue=True) triggers a nack+requeue.
            raise
