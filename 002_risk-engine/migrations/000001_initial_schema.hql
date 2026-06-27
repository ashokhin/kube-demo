-- Migration 000001: initial Hive schema for risk-engine
--
-- Hive migrations are FORWARD-ONLY. There are no rollback scripts.
-- Unlike PostgreSQL, Hive DDL has no transaction support.
-- To "roll back": write a new migration that reverses the change.
--
-- This script is idempotent: CREATE ... IF NOT EXISTS means it can be
-- safely re-run without failing if the objects already exist.

CREATE DATABASE IF NOT EXISTS risk;

-- Migration tracking table (equivalent of schema_migrations in PostgreSQL)
-- Stored as Parquet for efficient reads; not partitioned (small, append-only).
CREATE TABLE IF NOT EXISTS risk.schema_migrations (
    version     STRING     COMMENT 'Migration version, e.g. 000001',
    applied_at  TIMESTAMP  COMMENT 'UTC timestamp when migration was applied',
    description STRING     COMMENT 'Human-readable migration description'
)
STORED AS PARQUET;

-- Main results table, partitioned by date for efficient time-range queries.
-- Parquet + Snappy compression reduces storage by ~75% vs plain text.
CREATE TABLE IF NOT EXISTS risk.risk_results (
    portfolio_id    STRING   COMMENT 'Unique portfolio identifier',
    model_version   STRING   COMMENT 'Risk model version used for calculation',
    risk_score      DOUBLE   COMMENT 'Annualised portfolio volatility',
    var_95          DOUBLE   COMMENT 'Value-at-Risk at 95% confidence (daily, in portfolio currency)',
    var_99          DOUBLE   COMMENT 'Value-at-Risk at 99% confidence (daily, in portfolio currency)',
    total_value     DOUBLE   COMMENT 'Total portfolio market value',
    calculated_at   TIMESTAMP
)
PARTITIONED BY (dt STRING COMMENT 'Calculation date YYYY-MM-DD')
STORED AS PARQUET
TBLPROPERTIES (
    'parquet.compression' = 'SNAPPY',
    'transactional'       = 'false'
);

-- Record this migration as applied
INSERT INTO risk.schema_migrations
VALUES ('000001', current_timestamp(), 'initial schema: risk_results table');
