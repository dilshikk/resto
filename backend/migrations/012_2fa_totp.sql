-- Migration 012: add totp_secret to users for TOTP-based 2FA
--
-- is_2fa_enabled already existed since migration 001. This migration adds
-- the server-side secret that is generated during setup and used to validate
-- every TOTP code. The column is intentionally nullable: it is NULL until the
-- user completes the 2FA setup flow (setup → confirm first code → enabled).

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64);

COMMIT;
