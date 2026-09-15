#!/usr/bin/env bash
# ============================================================
# ContractIQ -- Production Backend Startup Script (Phase 20A)
#
# 1. Runs database migrations to latest schema head
# 2. Launches uvicorn production server on PORT (default: 8000)
# ============================================================

set -e

echo "[ContractIQ] Running database migrations (alembic upgrade head)..."
alembic upgrade head

PORT="${PORT:-8000}"
echo "[ContractIQ] Starting Uvicorn production server on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
