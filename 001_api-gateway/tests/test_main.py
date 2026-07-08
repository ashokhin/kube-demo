"""
Tests for api-gateway endpoints.

Strategy: replace the shared httpx.AsyncClient with httpx.MockTransport so that
no real network calls are made. The mock is injected directly into the module-level
variable `_http_client` — the same object that lifespan creates in production.

We use TestClient (synchronous) rather than AsyncClient to keep tests simple.
TestClient starts and stops the lifespan context manager automatically.
"""
import pytest
import httpx
from starlette.testclient import TestClient

import src.main as main_module
from src.main import app


@pytest.fixture(autouse=True)
def mock_http_client(respx_mock):
    """
    Inject a mock HTTP client before each test.

    respx_mock (from pytest-respx) intercepts httpx calls by pattern.
    We point _http_client at a client backed by respx_mock, which patches httpx
    globally for the duration of the test so all requests are intercepted.
    """
    client = httpx.AsyncClient(base_url="http://order-service")
    main_module._http_client = client
    yield
    # Reset to None after each test so tests are fully isolated.
    main_module._http_client = None


# Use TestClient without triggering lifespan (lifespan would overwrite our mock).
client = TestClient(app, raise_server_exceptions=True)


def test_healthz_returns_ok():
    # /healthz must always return 200 regardless of upstream state.
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_ok_when_upstream_healthy(respx_mock):
    respx_mock.get("http://order-service/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    resp = client.get("/readyz")
    assert resp.status_code == 200


def test_readyz_503_when_upstream_down(respx_mock):
    # Simulate a network failure from the upstream service.
    respx_mock.get("http://order-service/healthz").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    resp = client.get("/readyz")
    assert resp.status_code == 503


def test_create_order_proxies_request(respx_mock):
    respx_mock.post("http://order-service/orders").mock(
        return_value=httpx.Response(201, json={"id": "abc-123", "status": "pending"})
    )
    resp = client.post("/orders", json={"customer_id": "c1", "product_id": "p1", "quantity": 2})
    assert resp.status_code == 201
    assert resp.json()["id"] == "abc-123"


def test_create_order_forwards_upstream_4xx(respx_mock):
    # When order-service rejects the request (422), the gateway must forward
    # the same status code — not swallow it with a generic 500.
    respx_mock.post("http://order-service/orders").mock(
        return_value=httpx.Response(422, text="validation error")
    )
    resp = client.post("/orders", json={})
    assert resp.status_code == 422


def test_get_order_not_found(respx_mock):
    respx_mock.get("http://order-service/orders/missing").mock(
        return_value=httpx.Response(404, text="not found")
    )
    resp = client.get("/orders/missing")
    assert resp.status_code == 404
