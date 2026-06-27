"""
HDFS client wrapper.

In Kubernetes the pod uses Kerberos authentication (GSSAPI).
The KRB5CCNAME environment variable points to the ticket cache
maintained by the krb5-renewer sidecar container.

In mock mode (MOCK_MODE=true) the client returns synthetic data
so the service can run without any Hadoop infrastructure.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class HdfsClient:
    def __init__(self, hdfs_url: str, mock_mode: bool = False) -> None:
        self._mock = mock_mode
        self._url = hdfs_url
        if not mock_mode:
            self._connect()

    def _connect(self) -> None:
        # hdfs3 picks up Kerberos credentials from KRB5CCNAME automatically.
        # The ticket cache is written by the krb5-renewer sidecar and renewed every 8 hours.
        from hdfs3 import HDFileSystem
        self._fs = HDFileSystem(
            host=self._url.replace("hdfs://", "").split(":")[0],
            port=8020,
            krb_impersonation=False,  # use the service principal, not user impersonation
        )
        logger.info("Connected to HDFS", extra={"url": self._url, "krb5ccname": os.getenv("KRB5CCNAME")})

    def read_portfolio(self, portfolio_id: str, path: str) -> dict[str, Any]:
        """Read portfolio input data from HDFS as a dict."""
        if self._mock:
            logger.debug("MOCK: reading portfolio from HDFS", extra={"portfolio_id": portfolio_id})
            return {
                "portfolio_id": portfolio_id,
                "positions": [
                    {"asset": "AAPL", "quantity": 1000, "price": 185.0},
                    {"asset": "MSFT", "quantity": 500, "price": 415.0},
                    {"asset": "GOOGL", "quantity": 200, "price": 175.0},
                ],
            }
        import json
        file_path = f"{path}/{portfolio_id}/input.json"
        with self._fs.open(file_path) as f:
            data: dict[str, Any] = json.load(f)
        logger.info("Read portfolio from HDFS", extra={"path": file_path, "portfolio_id": portfolio_id})
        return data

    def write_result(self, portfolio_id: str, path: str, result: dict[str, Any]) -> None:
        """Write calculation results to HDFS as JSON."""
        if self._mock:
            logger.debug("MOCK: writing result to HDFS", extra={"portfolio_id": portfolio_id})
            return
        import json
        from datetime import date
        file_path = f"{path}/{portfolio_id}/{date.today().isoformat()}/result.json"
        with self._fs.open(file_path, "wb") as f:
            f.write(json.dumps(result).encode())
        logger.info("Wrote result to HDFS", extra={"path": file_path})
