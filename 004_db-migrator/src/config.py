from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    # DATABASE_URL is injected from Kubernetes Secret via envFrom.
    # Note: Alembic uses the synchronous psycopg2 driver (postgresql://),
    # not the async asyncpg driver (postgresql+asyncpg://) used by order-service.
    database_url: str = "postgresql://user:password@postgresql:5432/orders"

    model_config = ConfigDict(env_file=".env")


settings = Settings()
