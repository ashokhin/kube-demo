"""
Tests for order-service endpoints.

Strategy: patch `repository` and `publisher` modules with unittest.mock so that
no real database or RabbitMQ connection is required. This matches how the service
is structured — all external I/O is isolated in dedicated modules, making them
easy to replace in tests.
"""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from starlette.testclient import TestClient

from src.main import app
from src.models import Order

client = TestClient(app, raise_server_exceptions=True)


def _make_order(**kwargs) -> Order:
    """Build a minimal Order ORM object for use in mock return values."""
    defaults = {
        "id": "order-123",
        "customer_id": "customer-1",
        "product_id": "product-1",
        "quantity": 2,
        "status": "pending",
    }
    defaults.update(kwargs)
    order = Order(**defaults)
    return order


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_readyz_ok_when_all_dependencies_healthy():
    # Both DB and RabbitMQ must report healthy for the pod to receive traffic.
    with patch("src.main.repository.check_db_connection", new=AsyncMock(return_value=True)), \
         patch("src.main.publisher.check_connection", new=AsyncMock(return_value=True)):
        resp = client.get("/readyz")
    assert resp.status_code == 200


def test_readyz_503_when_db_unavailable():
    with patch("src.main.repository.check_db_connection", new=AsyncMock(return_value=False)), \
         patch("src.main.publisher.check_connection", new=AsyncMock(return_value=True)):
        resp = client.get("/readyz")
    assert resp.status_code == 503


def test_create_order_returns_201():
    order = _make_order()
    mock_publish = AsyncMock()
    with patch("src.main.repository.create_order", new=AsyncMock(return_value=order)), \
         patch("src.main.publisher.publish", new=mock_publish):
        resp = client.post("/orders", json={
            "customer_id": "customer-1",
            "product_id": "product-1",
            "quantity": 2,
        })
    assert resp.status_code == 201
    assert resp.json()["id"] == "order-123"
    assert resp.json()["status"] == "pending"
    # The event must be published so the notification-service picks it up.
    mock_publish.assert_called_once()
    args, _ = mock_publish.call_args
    assert args[0] == "order.created"


def test_get_order_found():
    order = _make_order()
    with patch("src.main.repository.get_order", new=AsyncMock(return_value=order)):
        resp = client.get("/orders/order-123")
    assert resp.status_code == 200
    assert resp.json()["id"] == "order-123"


def test_get_order_not_found():
    # repository returns None when the order does not exist in the DB.
    with patch("src.main.repository.get_order", new=AsyncMock(return_value=None)):
        resp = client.get("/orders/does-not-exist")
    assert resp.status_code == 404
