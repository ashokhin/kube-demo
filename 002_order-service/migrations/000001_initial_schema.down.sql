-- Migration: 000001_initial_schema (down)
-- Rolls back the initial schema.
--
-- WARNING: drops all order data. Run only in dev/test environments.
-- In production, rollback means deploying the previous application version,
-- not running migrate down.

DROP TABLE IF EXISTS orders;
