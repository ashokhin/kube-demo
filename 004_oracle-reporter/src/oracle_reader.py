"""
Oracle reader using python-oracledb thin mode.
Reads aggregated risk results for report generation.
"""
import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_MOCK_DATA = [
    {"portfolio_id": "PORTFOLIO_A", "model_version": "v1.0", "scenario": "base",
     "risk_score": 0.25, "var_95": 125_000.0, "var_99": 210_000.0,
     "calculated_date": (date.today() - timedelta(days=1)).isoformat()},
    {"portfolio_id": "PORTFOLIO_B", "model_version": "v1.0", "scenario": "stress",
     "risk_score": 0.41, "var_95": 320_000.0, "var_99": 540_000.0,
     "calculated_date": (date.today() - timedelta(days=1)).isoformat()},
]


class OracleReader:
    def __init__(self, dsn: str, user: str, password: str,
                 table: str, mock_mode: bool = False) -> None:
        self._mock = mock_mode
        self._table = table
        if not mock_mode:
            import oracledb
            self._conn = oracledb.connect(user=user, password=password, dsn=dsn)
            logger.info("Connected to Oracle", extra={"dsn": dsn, "user": user})

    def fetch_risk_summary(self, lookback_days: int) -> list[dict[str, Any]]:
        """Fetch aggregated risk results for the last N days."""
        if self._mock:
            logger.debug("MOCK: returning synthetic Oracle data")
            return _MOCK_DATA

        since = (date.today() - timedelta(days=lookback_days)).isoformat()
        sql = f"""
            SELECT
                portfolio_id,
                model_version,
                scenario,
                AVG(risk_score) AS risk_score,
                AVG(var_95)     AS var_95,
                AVG(var_99)     AS var_99,
                MAX(calculated_date) AS calculated_date
            FROM {self._table}
            WHERE calculated_date >= :since
            GROUP BY portfolio_id, model_version, scenario
            ORDER BY portfolio_id, calculated_date DESC
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, since=since)
            columns = [c[0].lower() for c in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.info("Fetched %d rows from Oracle", len(rows))
        return rows
