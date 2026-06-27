"""
Tests for db-migrator configuration.

The migration logic itself (env.py) requires a live database — it is tested
in integration/staging environments, not here. Unit tests cover only what can
be verified without a DB connection: configuration loading and migration file
structure.
"""
import importlib
import importlib.util
from pathlib import Path


def test_config_reads_database_url_from_env(monkeypatch):
    # Verify that settings picks up DATABASE_URL from the environment.
    # In Kubernetes this variable is injected from a Secret via envFrom.
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@testhost:5432/testdb")

    # Reload the module so pydantic-settings picks up the new env var.
    import src.config as config_module
    importlib.reload(config_module)

    assert config_module.settings.database_url == "postgresql://test:test@testhost:5432/testdb"


def test_config_uses_sync_driver():
    import src.config as config_module
    # Must use the synchronous psycopg2 driver (postgresql://),
    # not async asyncpg — Alembic is synchronous.
    assert config_module.settings.database_url.startswith("postgresql://")
    assert "+asyncpg" not in config_module.settings.database_url


def test_initial_migration_has_required_attributes():
    # Migration files can't be imported with a regular import (name starts with a digit),
    # so we load them via importlib.util. Alembic itself does the same internally.
    migration_path = Path(__file__).parent.parent / "src" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("migration_0001", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    # Every Alembic migration must define these four attributes and two functions.
    assert migration.revision == "0001"
    assert migration.down_revision is None  # first migration has no parent
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
