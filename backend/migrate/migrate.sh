#!/bin/sh
# ---------------------------------------------------------------------------
# MADO Checklist - database migration runner
#
# Applies every *.sql file from $MIGRATIONS_DIR in lexical order (001, 002 ...)
# exactly once and records it in the schema_migrations table.
#
# Connection settings come from the standard libpq variables:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
#
# Safe for existing databases: all migrations in this project are idempotent
# (IF NOT EXISTS / IF EXISTS), so on a database that was created earlier via
# docker-entrypoint-initdb.d the already-applied files are simply re-checked
# and recorded, and only the missing changes are actually applied.
# ---------------------------------------------------------------------------
set -eu

MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"
WAIT_RETRIES="${WAIT_RETRIES:-30}"

: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGPASSWORD:?PGPASSWORD is required (set POSTGRES_PASSWORD in .env)}"

# Hide "already exists, skipping" NOTICE spam from idempotent statements.
export PGOPTIONS="${PGOPTIONS:--c client_min_messages=warning}"

PSQL="psql -X -q -v ON_ERROR_STOP=1"

log() { echo "[migrate] $*"; }

# 1. Wait for the database -------------------------------------------------
attempt=0
until pg_isready -q; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$WAIT_RETRIES" ]; then
    log "database $PGHOST is not reachable after $WAIT_RETRIES attempts"
    exit 1
  fi
  log "waiting for database ($attempt/$WAIT_RETRIES)..."
  sleep 2
done

# 2. Tracking table ---------------------------------------------------------
$PSQL <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    VARCHAR(255) PRIMARY KEY,
    checksum    CHAR(64)     NOT NULL,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
SQL

# 3. Apply pending migrations ----------------------------------------------
applied=0
skipped=0

for file in "$MIGRATIONS_DIR"/*.sql; do
  if [ ! -e "$file" ]; then
    log "no migration files found in $MIGRATIONS_DIR"
    exit 1
  fi

  name=$(basename "$file")
  checksum=$(sha256sum "$file" | cut -d ' ' -f 1)

  recorded=$(echo "SELECT checksum FROM schema_migrations WHERE filename = :'name';" \
    | $PSQL -t -A -v name="$name")

  if [ -n "$recorded" ]; then
    if [ "$recorded" != "$checksum" ]; then
      log "WARNING: $name was modified after it had been applied (checksum mismatch). Not re-applying."
    fi
    skipped=$((skipped + 1))
    continue
  fi

  log "applying $name"
  $PSQL -f "$file"

  echo "INSERT INTO schema_migrations (filename, checksum) VALUES (:'name', :'checksum');" \
    | $PSQL -v name="$name" -v checksum="$checksum"

  applied=$((applied + 1))
done

log "done: $applied applied, $skipped already up to date"
