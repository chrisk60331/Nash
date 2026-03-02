#!/usr/bin/env bash
# =============================================================================
# Reset a Nash user's password
#
# Usage:
#   ./scripts/reset-password.sh <email> <new-password>
#   ./scripts/reset-password.sh nash@test.com MyNewPassword123
#
# Env vars:
#   NASH_URL             — base URL (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <email> <new-password>"
  exit 1
fi

EMAIL="$1"
PASSWORD="$2"
BASE_URL="${NASH_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

echo "Resetting password for ${EMAIL} at ${BASE_URL}..."

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/admin/reset-password" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}" \
  -d "{\"email\": \"${EMAIL}\", \"password\": \"${PASSWORD}\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "Password reset successfully."
else
  echo "Failed (HTTP ${HTTP_CODE}): ${BODY}"
  exit 1
fi
