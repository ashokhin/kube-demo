-- Migration 000002: add scenario column to risk_results
--
-- ALTER TABLE ADD COLUMNS appends to the schema without rewriting existing data.
-- Existing rows will return NULL for the new column — this is safe for Parquet.
-- No forward-fill needed: NULL scenario means "base" (pre-migration data).

ALTER TABLE risk.risk_results ADD COLUMNS (
    scenario STRING COMMENT 'Calculation scenario: base, stress, adverse'
);

INSERT INTO risk.schema_migrations
VALUES ('000002', current_timestamp(), 'add scenario column to risk_results');
