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
# psql exit codes: 1 = fatal (e.g. file not found), 2 = connection failed
# (wrong password / host), 3 = SQL error in a migration file.
# ---------------------------------------------------------------------------
set -eu

log() { echo "[migrate] $*"; }
fail() { echo "[migrate] ERROR: $*" >&2; exit 1; }

MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"
WAIT_RETRIES="${WAIT_RETRIES:-30}"

[ -n "${PGHOST:-}" ]     || fail "PGHOST is not set"
[ -n "${PGUSER:-}" ]     || fail "PGUSER is not set"
[ -n "${PGDATABASE:-}" ] || fail "PGDATABASE is not set"
[ -n "${PGPASSWORD:-}" ] || fail "PGPASSWORD is empty - set POSTGRES_PASSWORD in .env next to docker-compose.yml"

# Hide "already exists, skipping" NOTICE spam from idempotent statements.
export PGOPTIONS="${PGOPTIONS:--c client_min_messages=warning}"

PSQL="psql -X -q -v ON_ERROR_STOP=1"

log "target: $PGUSER@$PGHOST:${PGPORT:-5432}/$PGDATABASE"

# 1. Wait until the server accepts connections ------------------------------
attempt=0
until pg_isready -q; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt "$WAIT_RETRIES" ] || fail "database $PGHOST is not reachable after $WAIT_RETRIES attempts"
  log "waiting for database ($attempt/$WAIT_RETRIES)..."
  sleep 2
done

# 2. Verify credentials (pg_isready does NOT check the password) ------------
if ! auth_error=$($PSQL -t -A -c "SELECT 1" 2>&1 >/dev/null); then
  echo "$auth_error" >&2
  fail "cannot log in to the database.
Most common cause: POSTGRES_PASSWORD in .env differs from the password the
database volume was created with (Postgres only reads POSTGRES_PASSWORD on the
very first start of an empty volume). Fix without losing data:
  docker compose exec db psql -U $PGUSER -d $PGDATABASE -c \"ALTER USER $PGUSER PASSWORD '<value from .env>';\""
fi

# 3. Tracking table ---------------------------------------------------------
$PSQL -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    VARCHAR(255) PRIMARY KEY,
    checksum    CHAR(64)     NOT NULL,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);"

# 4. Apply pending migrations ----------------------------------------------
applied=0
skipped=0

for file in "$MIGRATIONS_DIR"/*.sql; do
  [ -e "$file" ] || fail "no migration files found in $MIGRATIONS_DIR"

  name=$(basename "$file")
  checksum=$(sha256sum "$file" | cut -d ' ' -f 1)

  recorded=$($PSQL -t -A -c "SELECT checksum FROM schema_migrations WHERE filename = '$name';")

  if [ -n "$recorded" ]; then
    if [ "$recorded" != "$checksum" ]; then
      log "WARNING: $name was modified after it had been applied (checksum mismatch). Not re-applying."
    fi
    skipped=$((skipped + 1))
    continue
  fi

  log "applying $name"
  if ! $PSQL -f "$file"; then
    fail "migration $name failed - see the SQL error above. Nothing after it was applied."
  fi

  $PSQL -c "INSERT INTO schema_migrations (filename, checksum) VALUES ('$name', '$checksum');"
  applied=$((applied + 1))
done

log "done: $applied applied, $skipped already up to date"
