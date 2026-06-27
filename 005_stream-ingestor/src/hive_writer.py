"""
Hive DDL for the risk_aggregates table used by stream-ingestor.

The table is created by the Hive migration (migrations/000003_risk_aggregates.hql).
This module only contains helper constants shared between stream_runner and tests.
"""

RISK_AGGREGATES_TABLE = "risk.risk_aggregates"

# Schema mirrors the Hive DDL in migrations/000003_risk_aggregates.hql
RISK_AGGREGATES_COLUMNS = [
    "dt",
    "model_version",
    "record_count",
    "avg_risk_score",
    "avg_var95",
    "avg_var99",
    "max_var99",
    "total_portfolio_value",
]
