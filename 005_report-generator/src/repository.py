from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from sqlalchemy import create_engine, text

from src.config import settings

# Synchronous engine: report-generator is a CronJob (batch process), not a server.
# Using sync SQLAlchemy avoids async boilerplate for a script that runs once and exits.
engine = create_engine(settings.database_url, echo=False)


@dataclass
class OrderSummary:
    total_orders: int
    pending: int
    confirmed: int
    cancelled: int
    period_start: datetime
    period_end: datetime


def fetch_order_summary() -> OrderSummary:
    period_end = datetime.now(tz=timezone.utc)
    period_start = period_end - timedelta(days=settings.report_period_days)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_orders,
                    SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                FROM orders
                WHERE created_at >= :start AND created_at < :end
                """
            ),
            {"start": period_start, "end": period_end},
        ).fetchone()

    # The query always returns exactly one row (COUNT never returns NULL),
    # but individual SUM columns are NULL if no rows match — coerce to 0.
    return OrderSummary(
        total_orders=row.total_orders or 0,
        pending=row.pending or 0,
        confirmed=row.confirmed or 0,
        cancelled=row.cancelled or 0,
        period_start=period_start,
        period_end=period_end,
    )
