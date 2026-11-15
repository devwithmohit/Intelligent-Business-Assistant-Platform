#!/usr/bin/env sh
set -e

echo "[IBA] Applying database migrations with Alembic..."
alembic upgrade head

echo "[IBA] Launching backend server..."
exec "$@"
