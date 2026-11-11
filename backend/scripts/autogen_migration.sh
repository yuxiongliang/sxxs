#!/usr/bin/env bash
# Generate a migration against a *clean* database built from the migration
# history, never against a long-lived development database.
#
# A dev DB that was once created by `Base.metadata.create_all` (the pre-Alembic
# path) carries legacy artefacts -- unnamed constraints, a stale `users.role`
# foreign key, implicit server defaults. Autogenerating against it produces
# destructive noise (drop_constraint on unnamed constraints fails at runtime).
#
# Usage: scripts/autogen_migration.sh "add cart tables"
set -euo pipefail

MESSAGE="${1:?usage: $0 \"migration message\"}"
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH_DB="${AUTOGEN_DB:-ant_design_pro_autogen}"
PG_USER="${PGUSER:-$(whoami)}"
PG_PORT="${PGPORT:-5433}"

cd "$BACKEND_DIR"

python_bin=".venv/bin/python"

psql -p "$PG_PORT" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};" >/dev/null
psql -p "$PG_PORT" -d postgres -c "CREATE DATABASE ${SCRATCH_DB};" >/dev/null

URL="postgresql+asyncpg://${PG_USER}@127.0.0.1:${PG_PORT}/${SCRATCH_DB}"
ALEMBIC_DATABASE_URL="$URL" "$python_bin" -m alembic upgrade head
ALEMBIC_DATABASE_URL="$URL" "$python_bin" -m alembic revision --autogenerate -m "$MESSAGE"

psql -p "$PG_PORT" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};" >/dev/null
echo "migration generated; review it before committing"
