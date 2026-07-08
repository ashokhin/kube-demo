from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    # DATABASE_URL is sensitive — injected from Kubernetes Secret.
    # Note: synchronous SQLAlchemy (no async) — this is a batch Job, not a server.
    database_url: str = "postgresql://user:password@postgresql:5432/orders"
    # REPORT_OUTPUT_PATH maps to a PersistentVolumeClaim mounted at /data/reports.
    # The PVC is managed outside the Helm chart to prevent data loss on helm uninstall.
    report_output_path: str = "/tmp/reports"
    report_period_days: int = 7
    log_level: str = "INFO"

    model_config = ConfigDict(env_file=".env")


settings = Settings()
