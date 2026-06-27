import logging
import logging.config
import sys

from src.config import settings
from src.repository import fetch_order_summary
from src.renderer import render_json, render_csv

logging.config.dictConfig(
    {
        "version": 1,
        "formatters": {
            "json": {
                "()": "logging.Formatter",
                "fmt": '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
            }
        },
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
        "root": {"level": settings.log_level, "handlers": ["console"]},
    }
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "report generation started",
        extra={"period_days": settings.report_period_days, "output": settings.report_output_path},
    )

    try:
        summary = fetch_order_summary()
        json_path = render_json(summary, settings.report_output_path)
        csv_path = render_csv(summary, settings.report_output_path)
        logger.info(
            "report generation completed",
            extra={
                "total_orders": summary.total_orders,
                "json": json_path,
                "csv": csv_path,
            },
        )
    except Exception as exc:
        logger.error("report generation failed", extra={"error": str(exc)})
        # Non-zero exit code marks the CronJob pod as Failed.
        # Kubernetes will retry according to the Job's backoffLimit.
        sys.exit(1)


if __name__ == "__main__":
    main()
