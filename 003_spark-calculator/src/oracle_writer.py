"""
Oracle writer using python-oracledb (thin mode).

python-oracledb is Oracle's official Python driver (replaces cx_Oracle since 2022).
Key advantage: "thin mode" requires NO Oracle Instant Client installation.
The driver is pure Python + a small C extension — installs via pip like any package.

Thick mode (with Instant Client) is available for features like Advanced Queuing,
but thin mode covers all standard SQL operations needed here.

See: https://python-oracledb.readthedocs.io/en/latest/user_guide/initialization.html
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory store for mock mode
_mock_store: list[dict[str, Any]] = []


class OracleWriter:
    def __init__(self, dsn: str, user: str, password: str,
                 table: str, mock_mode: bool = False) -> None:
        self._mock = mock_mode
        self._dsn = dsn
        self._user = user
        self._table = table
        if not mock_mode:
            import oracledb
            # thin=True: no Oracle Instant Client needed.
            # Kerberos auth to Oracle is handled separately via OS-level KRB5 config
            # if Oracle DB is Kerberos-enabled. For this demo we use password auth.
            self._conn = oracledb.connect(user=user, password=password, dsn=dsn)
            logger.info("Connected to Oracle", extra={"dsn": dsn, "user": user})

    def write_results(self, results: list[dict[str, Any]]) -> None:
        """Bulk-insert Spark calculation results into Oracle."""
        if self._mock:
            _mock_store.extend(results)
            logger.debug("MOCK: wrote %d rows to Oracle", len(results))
            return

        sql = f"""
            MERGE INTO {self._table} t
            USING (SELECT :portfolio_id AS portfolio_id,
                          :model_version AS model_version,
                          :scenario AS scenario,
                          :risk_score AS risk_score,
                          :var_95 AS var_95,
                          :var_99 AS var_99,
                          :calculated_date AS calculated_date
                     FROM dual) s
            ON (t.portfolio_id = s.portfolio_id
                AND t.model_version = s.model_version
                AND t.scenario = s.scenario
                AND t.calculated_date = s.calculated_date)
            WHEN MATCHED THEN UPDATE SET
                t.risk_score = s.risk_score,
                t.var_95 = s.var_95,
                t.var_99 = s.var_99
            WHEN NOT MATCHED THEN INSERT
                (portfolio_id, model_version, scenario, risk_score, var_95, var_99, calculated_date)
            VALUES
                (s.portfolio_id, s.model_version, s.scenario,
                 s.risk_score, s.var_95, s.var_99, s.calculated_date)
        """
        with self._conn.cursor() as cursor:
            cursor.executemany(sql, results)
        self._conn.commit()
        logger.info("Wrote %d rows to Oracle table %s", len(results), self._table)

    def get_mock_store(self) -> list[dict[str, Any]]:
        return _mock_store
