from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from src.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url from alembic.ini with the value from the environment.
# This ensures the DB URL comes from a Kubernetes Secret at runtime,
# not from a hardcoded value in the config file.
config.set_main_option("sqlalchemy.url", settings.database_url)

# target_metadata=None means Alembic does not compare against ORM models.
# Migrations are written manually in versions/ — there is no autogenerate.
target_metadata = None


def run_migrations_offline() -> None:
    # Offline mode generates SQL scripts without connecting to the DB.
    # Useful for review before applying, or for environments without direct DB access.
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Online mode connects to the DB and applies migrations immediately.
    # NullPool is used so the connection is closed after migrations complete —
    # this is a short-lived Job, not a long-running server with a connection pool.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
