-- Migration 019 — role_ids on checklist_templates and checklists
--
-- Problem: templates had no concept of "which position/role this checklist
-- is for". The bot and web panel showed every checklist for the employee's
-- branch, regardless of role — e.g. a waiter saw the cook's checklists.
--
-- Fix: templates gain a `role_ids` array. An empty array means "applies to
-- every role" (unchanged behaviour, backward compatible). A non-empty array
-- restricts the template to only those role ids.
--
-- `checklists.role_ids` is a denormalized copy of the template's role_ids at
-- creation time, same pattern already used for template_name — so editing a
-- template later never changes checklists already generated.
--
-- Idempotent: safe to run several times and on existing databases.

ALTER TABLE checklist_templates
    ADD COLUMN IF NOT EXISTS role_ids INTEGER[] NOT NULL DEFAULT '{}';

ALTER TABLE checklists
    ADD COLUMN IF NOT EXISTS role_ids INTEGER[] NOT NULL DEFAULT '{}';
