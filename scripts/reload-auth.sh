#!/usr/bin/env bash
# =============================================================================
# Reload auth cache on a Nash instance (forces re-read from Backboard)
#
# Usage:
#   ./scripts/reload-auth.sh
#   NASH_URL=https://xyz.us-west-2.awsapprunner.com ./scripts/reload-auth.sh
#
# Env vars:
#   NASH_URL             — base URL (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

BASE_URL="${NASH_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

echo "Reloading auth cache at ${BASE_URL}..."

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/admin/reload-auth" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "Auth cache reloaded."
else
  echo "Failed (HTTP ${HTTP_CODE}): ${BODY}"
  exit 1
fi
