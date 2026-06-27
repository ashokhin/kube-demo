"""
Integration tests for risk-engine FastAPI endpoints.
Runs with MOCK_MODE=true — no real HDFS or Hive required.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os

os.environ["MOCK_MODE"] = "true"

from src.main import app

client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_returns_ok_in_mock_mode():
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["mock_mode"] is True


def test_calculate_returns_risk_result():
    response = client.post("/api/calculate", json={
        "portfolioId": "TEST_PORT_001",
        "modelVersion": "v1.0",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["portfolio_id"] == "TEST_PORT_001"
    assert "risk_score" in data
    assert "var_95" in data
    assert "var_99" in data


def test_calculate_increments_hive_mock_store():
    from src.main import hive
    initial_count = len(hive.get_mock_store())
    client.post("/api/calculate", json={
        "portfolioId": "PORT_FOR_HIVE_TEST",
        "modelVersion": "v2.0",
    })
    assert len(hive.get_mock_store()) == initial_count + 1
