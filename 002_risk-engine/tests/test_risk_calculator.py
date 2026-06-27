"""
Tests for risk_calculator — pure Python logic, no Hadoop/Hive needed.
"""
import pytest
from src import risk_calculator


SAMPLE_PORTFOLIO = {
    "portfolio_id": "TEST_PORT_001",
    "positions": [
        {"asset": "AAPL", "quantity": 1000, "price": 185.0},
        {"asset": "MSFT", "quantity": 500, "price": 415.0},
    ],
}


def test_calculate_returns_all_required_fields():
    result = risk_calculator.calculate(SAMPLE_PORTFOLIO, "v1.0")
    assert "portfolio_id" in result
    assert "model_version" in result
    assert "risk_score" in result
    assert "var_95" in result
    assert "var_99" in result
    assert "total_value" in result
    assert "calculated_date" in result


def test_calculate_portfolio_id_matches_input():
    result = risk_calculator.calculate(SAMPLE_PORTFOLIO, "v1.0")
    assert result["portfolio_id"] == "TEST_PORT_001"
    assert result["model_version"] == "v1.0"


def test_calculate_var_99_greater_than_var_95():
    result = risk_calculator.calculate(SAMPLE_PORTFOLIO, "v1.0")
    assert result["var_99"] > result["var_95"] > 0


def test_calculate_total_value_correct():
    result = risk_calculator.calculate(SAMPLE_PORTFOLIO, "v1.0")
    expected = 1000 * 185.0 + 500 * 415.0
    assert result["total_value"] == expected


def test_calculate_empty_portfolio_returns_zero_risk():
    empty = {"portfolio_id": "EMPTY", "positions": []}
    result = risk_calculator.calculate(empty, "v1.0")
    assert result["risk_score"] == 0.0
    assert result["var_95"] == 0.0
    assert result["var_99"] == 0.0


def test_calculate_unknown_asset_uses_default_volatility():
    portfolio = {
        "portfolio_id": "UNKNOWN_ASSETS",
        "positions": [{"asset": "UNKNOWN_TICKER", "quantity": 100, "price": 50.0}],
    }
    result = risk_calculator.calculate(portfolio, "v1.0")
    # Should not raise — uses DEFAULT volatility
    assert result["risk_score"] > 0
