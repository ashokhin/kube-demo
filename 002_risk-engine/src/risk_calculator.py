"""
Risk calculation logic — pure Python, no Hadoop dependencies.

This module is intentionally simple (a demo VaR approximation).
In a real model: replace with your quantitative library (QuantLib, riskpy, etc.)
"""
import logging
import math
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# Simulated volatilities per asset (annualised, in demo these are constants)
_VOLATILITY: dict[str, float] = {
    "AAPL": 0.28,
    "MSFT": 0.24,
    "GOOGL": 0.31,
    "DEFAULT": 0.30,
}

# Standard normal quantiles for VaR
_Z_95 = 1.645
_Z_99 = 2.326


def calculate(portfolio: dict[str, Any], model_version: str) -> dict[str, Any]:
    """
    Calculate portfolio risk score and Value-at-Risk (VaR) at 95% and 99% confidence.

    Returns a result dict ready to be written to Hive.
    """
    positions = portfolio.get("positions", [])
    portfolio_id = portfolio.get("portfolio_id", "unknown")

    if not positions:
        logger.warning("Empty portfolio — returning zero risk", extra={"portfolio_id": portfolio_id})
        return _zero_result(portfolio_id, model_version)

    # Portfolio value and weighted variance (simplified: no correlation matrix)
    total_value = sum(p["quantity"] * p["price"] for p in positions)
    weighted_variance = sum(
        (p["quantity"] * p["price"] / total_value) ** 2
        * _VOLATILITY.get(p["asset"], _VOLATILITY["DEFAULT"]) ** 2
        for p in positions
    )
    portfolio_volatility = math.sqrt(weighted_variance)

    # Daily VaR = portfolio_value * z * daily_vol  (annual vol / sqrt(252))
    daily_vol = portfolio_volatility / math.sqrt(252)
    var_95 = total_value * _Z_95 * daily_vol
    var_99 = total_value * _Z_99 * daily_vol
    risk_score = portfolio_volatility  # simplified risk score = annualised vol

    result = {
        "portfolio_id": portfolio_id,
        "model_version": model_version,
        "risk_score": round(risk_score, 6),
        "var_95": round(var_95, 2),
        "var_99": round(var_99, 2),
        "total_value": round(total_value, 2),
        "calculated_date": date.today().isoformat(),
    }
    logger.info("Risk calculated",
                extra={"portfolio_id": portfolio_id, "risk_score": risk_score, "var_99": var_99})
    return result


def _zero_result(portfolio_id: str, model_version: str) -> dict[str, Any]:
    return {
        "portfolio_id": portfolio_id,
        "model_version": model_version,
        "risk_score": 0.0,
        "var_95": 0.0,
        "var_99": 0.0,
        "total_value": 0.0,
        "calculated_date": date.today().isoformat(),
    }
