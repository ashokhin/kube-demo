from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # pydantic-settings reads each field from the matching env var automatically.
    # Field name "order_service_url" maps to env var ORDER_SERVICE_URL.
    # In Kubernetes the env var is injected from a ConfigMap via envFrom.
    # The default value is used only for local development.
    order_service_url: str = "http://order-service:8080"
    port: int = 8080
    log_level: str = "INFO"

    class Config:
        # In local development, pydantic-settings also reads from .env file.
        # In Kubernetes, .env does not exist — env vars come from ConfigMap/Secret.
        env_file = ".env"


# Module-level singleton: settings are read once at import time.
# All modules import this object; there is no need to call Settings() again.
settings = Settings()
