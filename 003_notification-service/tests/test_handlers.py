"""
Tests for notification-service message dispatch logic.

The consumer (RabbitMQ) is not tested here — it requires a real broker.
We test the dispatch() function in isolation using a temporary YAML config file
so tests do not depend on the bundled handlers_config.yaml content.
"""
import pytest
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml


SAMPLE_CONFIG = textwrap.dedent("""\
    handlers:
      order.created:
        - type: email
          template: order_confirmation
          retry: 3
        - type: push
          template: order_created_push
          retry: 1
      order.shipped:
        - type: sms
          template: order_shipped_sms
          retry: 2
    default:
      - type: log
        level: warning
""")


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    """Write a known-good config to a temp file and return its path."""
    cfg = tmp_path / "handlers_config.yaml"
    cfg.write_text(SAMPLE_CONFIG)
    return cfg


@pytest.mark.asyncio
async def test_dispatch_known_event_dispatches_channels(config_file: Path):
    # dispatch() should call _dispatch_channels with the channels for the event.
    with patch.dict("os.environ", {"HANDLERS_CONFIG_PATH": str(config_file)}):
        # Reload module so _routing is loaded from the temp file.
        import importlib
        import src.handlers as handlers_mod
        importlib.reload(handlers_mod)

        with patch.object(handlers_mod, "_dispatch_channels", new=AsyncMock()) as mock_dispatch:
            await handlers_mod.dispatch("order.created", {"order_id": "abc"})

    mock_dispatch.assert_awaited_once()
    _, kwargs = mock_dispatch.call_args
    # First positional arg is event_type
    args = mock_dispatch.call_args.args
    assert args[0] == "order.created"
    assert len(args[1]) == 2  # email + push channels


@pytest.mark.asyncio
async def test_dispatch_unknown_event_uses_default_fallback(config_file: Path):
    # Unknown event type must fall through to the default channel list,
    # not raise an exception (unknown events must not block the queue).
    with patch.dict("os.environ", {"HANDLERS_CONFIG_PATH": str(config_file)}):
        import importlib
        import src.handlers as handlers_mod
        importlib.reload(handlers_mod)

        with patch.object(handlers_mod, "_dispatch_channels", new=AsyncMock()) as mock_dispatch:
            await handlers_mod.dispatch("order.no_such_event", {})

    mock_dispatch.assert_awaited_once()
    args = mock_dispatch.call_args.args
    assert args[0] == "order.no_such_event"
    # Default channel list from SAMPLE_CONFIG: one entry with type=log
    assert args[1] == [{"type": "log", "level": "warning"}]


@pytest.mark.asyncio
async def test_dispatch_propagates_handler_exception(config_file: Path):
    # If _dispatch_channels raises, dispatch() must re-raise so the consumer
    # can nack+requeue the message.
    with patch.dict("os.environ", {"HANDLERS_CONFIG_PATH": str(config_file)}):
        import importlib
        import src.handlers as handlers_mod
        importlib.reload(handlers_mod)

        with patch.object(
            handlers_mod, "_dispatch_channels",
            new=AsyncMock(side_effect=RuntimeError("downstream failed"))
        ):
            with pytest.raises(RuntimeError, match="downstream failed"):
                await handlers_mod.dispatch("order.created", {"order_id": "x"})


def test_load_routing_config_reads_yaml_correctly(config_file: Path):
    # _load_routing_config() should parse the YAML file and return a dict.
    import importlib
    import src.handlers as handlers_mod
    importlib.reload(handlers_mod)

    config = handlers_mod._load_routing_config(str(config_file))

    assert "handlers" in config
    assert "order.created" in config["handlers"]
    assert "default" in config
    assert config["default"][0]["type"] == "log"
