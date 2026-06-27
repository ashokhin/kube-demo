"""
Tests for spark-calculator.
All tests run with MOCK_MODE=true — no real Spark, Hive, or Oracle needed.
"""
import os
import pytest

os.environ["MOCK_MODE"] = "true"
os.environ["PORTFOLIO_ID"] = "TEST_PORT"
os.environ["MODEL_VERSION"] = "v1.0"
os.environ["SCENARIO"] = "base"

from src.main import compute, run
from src.oracle_writer import OracleWriter


def test_compute_mock_returns_synthetic_result():
    results = compute(spark=None, portfolio_id="TEST_PORT", model_version="v1.0", scenario="base")
    assert len(results) == 1
    row = results[0]
    assert row["portfolio_id"] == "TEST_PORT"
    assert row["model_version"] == "v1.0"
    assert row["scenario"] == "base"
    assert row["risk_score"] > 0
    assert row["var_99"] > row["var_95"] > 0


def test_oracle_writer_mock_stores_results():
    writer = OracleWriter(
        dsn="localhost/ORCLPDB1",
        user="test",
        password="test",
        table="test_table",
        mock_mode=True,
    )
    results = [{"portfolio_id": "P1", "risk_score": 0.3, "var_95": 100.0, "var_99": 150.0}]
    writer.write_results(results)
    store = writer.get_mock_store()
    assert any(r["portfolio_id"] == "P1" for r in store)


def test_run_completes_without_errors():
    # Full end-to-end run in mock mode — should not raise
    run()
