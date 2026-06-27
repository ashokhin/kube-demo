"""
spark-calculator entry point.

This is a Kubernetes Job — it runs to completion and exits.
risk-ui launches it via the Kubernetes API with model_version, portfolio_id, scenario
injected as environment variables.

Pipeline:
  1. Create SparkSession (mode: submit / operator / yarn)
  2. Read risk_results from Hive (input data)
  3. Calculate aggregated Spark-based risk metrics
  4. Write results to Oracle
  5. Exit 0 (success) or non-zero (failure → Kubernetes retries per backoffLimit)
"""
import logging
import os
import sys
from datetime import date
from typing import Any

from src.config import settings
from src.spark_runner import create_spark_session
from src.oracle_writer import OracleWriter

logging.basicConfig(
    level=settings.log_level.upper(),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run() -> None:
    logger.info("spark-calculator starting",
                extra={
                    "model_version": settings.model_version,
                    "portfolio_id": settings.portfolio_id,
                    "scenario": settings.scenario,
                    "spark_mode": settings.spark_mode,
                    "mock_mode": settings.mock_mode,
                })

    # Set KRB5CCNAME so Spark and PyHive use the ticket from the init container.
    if not settings.mock_mode:
        os.environ["KRB5CCNAME"] = settings.krb5ccname

    spark = create_spark_session(
        mode=settings.spark_mode,
        app_name=settings.spark_app_name,
        mock_mode=settings.mock_mode,
    )

    results = compute(spark, settings.portfolio_id, settings.model_version, settings.scenario)

    writer = OracleWriter(
        dsn=settings.oracle_dsn,
        user=settings.oracle_user,
        password=settings.oracle_password,
        table=settings.oracle_table,
        mock_mode=settings.mock_mode,
    )
    writer.write_results(results)

    if spark:
        spark.stop()

    logger.info("spark-calculator completed", extra={"rows_written": len(results)})


def compute(spark, portfolio_id: str, model_version: str, scenario: str) -> list[dict[str, Any]]:
    """
    Read Hive input, compute aggregated risk metrics in Spark, return result rows.
    In mock mode: return synthetic data without touching Hive.
    """
    if spark is None:
        # Mock mode — return synthetic results
        logger.info("MOCK: returning synthetic risk results")
        return [{
            "portfolio_id": portfolio_id,
            "model_version": model_version,
            "scenario": scenario,
            "risk_score": 0.25,
            "var_95": 125_000.0,
            "var_99": 210_000.0,
            "calculated_date": date.today().isoformat(),
        }]

    # Read the latest day's risk results for this portfolio from Hive
    df = spark.sql(f"""
        SELECT
            portfolio_id,
            model_version,
            AVG(risk_score)  AS risk_score,
            SUM(var_95)      AS var_95,
            SUM(var_99)      AS var_99,
            MAX(dt)          AS calculated_date
        FROM {settings.hive_database}.{settings.hive_table}
        WHERE portfolio_id = '{portfolio_id}'
          AND model_version = '{model_version}'
          AND dt = (SELECT MAX(dt) FROM {settings.hive_database}.{settings.hive_table}
                    WHERE portfolio_id = '{portfolio_id}')
        GROUP BY portfolio_id, model_version
    """)

    # Collect is safe here: the result is a single aggregated row per portfolio.
    # For large multi-portfolio runs, use df.write.jdbc() directly instead of collect().
    rows = df.collect()
    return [
        {
            "portfolio_id": row["portfolio_id"],
            "model_version": row["model_version"],
            "scenario": scenario,
            "risk_score": float(row["risk_score"]),
            "var_95": float(row["var_95"]),
            "var_99": float(row["var_99"]),
            "calculated_date": row["calculated_date"],
        }
        for row in rows
    ]


if __name__ == "__main__":
    run()
