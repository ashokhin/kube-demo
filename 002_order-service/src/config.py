from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Sensitive values (DATABASE_URL, RABBITMQ_URL) come from Kubernetes Secret.
    # Non-sensitive values (ORDERS_EXCHANGE, LOG_LEVEL, PORT) come from ConfigMap.
    # Both are injected as env vars via envFrom in the Deployment spec.
    # The defaults below are used only in local development.
    database_url: str = "postgresql+asyncpg://user:password@postgresql:5432/orders"
    rabbitmq_url: str = "amqp://user:password@rabbitmq:5672/"
    # Exchange name is non-sensitive: it is a routing concept, not a credential.
    orders_exchange: str = "orders"
    port: int = 8080
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
