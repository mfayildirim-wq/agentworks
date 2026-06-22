#!/usr/bin/env bash
# Backend-Tests im agentworks-backend-Image gegen den gemounteten Arbeitsbaum + Test-DB.
# Nutzung: scripts/run-backend-tests.sh [pytest-args...]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm --network awtest \
  -e DATABASE_URL="postgresql+asyncpg://agentworks:agentworks_dev@agentworks-testdb:5432/agentworks_test" \
  -e REDIS_URL="redis://agentworks-testdb:6379/15" \
  -e AUTH_DISABLED_FOR_TESTS=1 \
  -v "$REPO/backend:/app/backend" \
  -w /app/backend \
  agentworks-backend \
  sh -lc 'pip install -q "pytest>=8" "pytest-asyncio==0.23.8" pypdf python-docx >/dev/null 2>&1; pytest "$@"' _ "$@"
