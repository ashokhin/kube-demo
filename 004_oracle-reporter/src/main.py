"""
oracle-reporter entry point — Kubernetes CronJob.

Runs to completion and exits. No HTTP server.
Pipeline:
  1. Read aggregated risk data from Oracle
  2. Render HTML report via Jinja2
  3. Upload report to HDFS
"""
import logging
import os
import sys
import tempfile
from datetime import date

from src.config import settings
from src.oracle_reader import OracleReader
from src.report_renderer import render_html

logging.basicConfig(
    level=settings.log_level.upper(),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run() -> None:
    logger.info("oracle-reporter starting",
                extra={"mock_mode": settings.mock_mode,
                       "lookback_days": settings.report_lookback_days})

    if not settings.mock_mode:
        os.environ["KRB5CCNAME"] = settings.krb5ccname

    reader = OracleReader(
        dsn=settings.oracle_dsn,
        user=settings.oracle_user,
        password=settings.oracle_password,
        table=settings.oracle_source_table,
        mock_mode=settings.mock_mode,
    )

    rows = reader.fetch_risk_summary(settings.report_lookback_days)
    logger.info("Fetched %d rows from Oracle", len(rows))

    # Render to a temp file, then upload to HDFS
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        local_path = tmp.name

    render_html(rows, local_path)

    hdfs_path = f"{settings.hdfs_output_path}/{date.today().isoformat()}/risk_report.html"
    _upload_to_hdfs(local_path, hdfs_path)

    os.unlink(local_path)
    logger.info("oracle-reporter completed", extra={"hdfs_path": hdfs_path})


def _upload_to_hdfs(local_path: str, hdfs_path: str) -> None:
    if settings.mock_mode:
        logger.debug("MOCK: skipping HDFS upload", extra={"hdfs_path": hdfs_path})
        return

    from hdfs3 import HDFileSystem
    host = settings.hdfs_url.replace("hdfs://", "").split(":")[0]
    fs = HDFileSystem(host=host, port=8020)
    fs.put(local_path, hdfs_path)
    logger.info("Uploaded report to HDFS", extra={"path": hdfs_path})


if __name__ == "__main__":
    run()
