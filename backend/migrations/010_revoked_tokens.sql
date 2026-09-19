-- Migration 010: JWT revocation denylist
-- Note: the backend also creates this table automatically at startup via
-- SQLAlchemy's Base.metadata.create_all (see app/main.py lifespan), since it's
-- a brand-new table with no ALTER needed on existing rows. This file exists so
-- a fresh `docker compose up` that seeds via docker-entrypoint-initdb.d has it
-- too, and for parity with the rest of the numbered migrations.

BEGIN;

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti         VARCHAR(36) PRIMARY KEY,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS revoked_tokens_expires_idx ON revoked_tokens(expires_at);

COMMIT;
