from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    # RABBITMQ_URL is sensitive (credentials) — injected from Kubernetes Secret.
    # QUEUE_NAME, LOG_LEVEL, PORT are non-sensitive — injected from ConfigMap.
    # All are provided via envFrom in the Deployment spec.
    rabbitmq_url: str = "amqp://user:password@rabbitmq:5672/"
    queue_name: str = "notifications"
    port: int = 8080
    log_level: str = "INFO"

    model_config = ConfigDict(env_file=".env")


settings = Settings()
