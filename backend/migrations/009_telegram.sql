-- Migration 009: link employees to their Telegram account
-- telegram_id is set once the employee links their account in the bot via /start + invite code.

ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS telegram_id BIGINT UNIQUE;
