-- Migration 000003: create risk_aggregates table for stream-ingestor output
-- Applied by: beeline via migrate.sh (same runner as risk-engine migrations)
-- Forward-only: Hive DDL has no transaction support, no rollback script.

CREATE TABLE IF NOT EXISTS risk.risk_aggregates (
    model_version       STRING,
    record_count        BIGINT,
    avg_risk_score      DOUBLE,
    avg_var95           DOUBLE,
    avg_var99           DOUBLE,
    max_var99           DOUBLE,
    total_portfolio_value DOUBLE
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

INSERT INTO risk.schema_migrations VALUES (
    '000003',
    current_timestamp(),
    'risk_aggregates table for Spark Structured Streaming output'
);
