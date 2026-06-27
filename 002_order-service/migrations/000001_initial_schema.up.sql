-- Migration: 000001_initial_schema (up)
-- Creates the initial orders table.
--
-- golang-migrate applies files in numeric order and tracks applied migrations
-- in the schema_migrations table (created automatically on first run).
-- Running this migration twice is safe — golang-migrate skips already-applied versions.

CREATE TABLE IF NOT EXISTS orders (
    id          VARCHAR     NOT NULL PRIMARY KEY,
    customer_id VARCHAR     NOT NULL,
    product_id  VARCHAR     NOT NULL,
    quantity    INTEGER     NOT NULL,
    status      VARCHAR     NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
