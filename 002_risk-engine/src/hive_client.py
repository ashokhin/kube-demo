"""
Hive client wrapper using PyHive with GSSAPI (Kerberos) authentication.

Connection flow in Kubernetes:
  1. krb5-renewer sidecar maintains a valid TGT in /tmp/krb5/tgt
  2. KRB5CCNAME env var points to that file
  3. PyHive uses sasl + thrift-sasl to authenticate via GSSAPI
  4. Hive server validates the Kerberos ticket and allows the connection

In mock mode the client writes to an in-memory dict instead of real Hive.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory store used when MOCK_MODE=true
_mock_store: list[dict[str, Any]] = []


class HiveClient:
    def __init__(self, host: str, port: int, database: str, mock_mode: bool = False) -> None:
        self._mock = mock_mode
        self._host = host
        self._port = port
        self._database = database
        if not mock_mode:
            self._connect()

    def _connect(self) -> None:
        from pyhive import hive
        # auth="GSSAPI" uses the KRB5CCNAME ticket cache for authentication.
        # No username/password needed — the Kerberos principal is the identity.
        self._conn = hive.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            auth="GSSAPI",
        )
        self._cursor = self._conn.cursor()
        logger.info("Connected to Hive", extra={"host": self._host, "database": self._database})

    def write_risk_result(self, result: dict[str, Any]) -> None:
        """Insert a risk calculation result row into Hive."""
        if self._mock:
            _mock_store.append(result)
            logger.debug("MOCK: wrote risk result to Hive", extra={"portfolio_id": result.get("portfolio_id")})
            return

        # Hive INSERT uses dynamic partition (dt column).
        # HIVE_EXEC_DYNAMIC_PARTITION must be enabled on the Hive server.
        self._cursor.execute("""
            INSERT INTO risk.risk_results
                PARTITION (dt = %(dt)s)
            VALUES (
                %(portfolio_id)s,
                %(model_version)s,
                %(risk_score)s,
                %(var_95)s,
                %(var_99)s,
                current_timestamp()
            )
        """, {
            "dt": result["calculated_date"],
            "portfolio_id": result["portfolio_id"],
            "model_version": result["model_version"],
            "risk_score": result["risk_score"],
            "var_95": result["var_95"],
            "var_99": result["var_99"],
        })
        logger.info("Wrote risk result to Hive",
                    extra={"portfolio_id": result["portfolio_id"], "risk_score": result["risk_score"]})

    def get_mock_store(self) -> list[dict[str, Any]]:
        """Returns mock in-memory store — for testing only."""
        return _mock_store
