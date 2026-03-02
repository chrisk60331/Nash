#!/usr/bin/env bash
# =============================================================================
# Delete a Nash user by email
#
# Usage:
#   ./scripts/delete-user.sh <email>
#   ./scripts/delete-user.sh nash@test.com
#
# Env vars:
#   NASH_URL             — base URL (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <email>"
  exit 1
fi

EMAIL="$1"
BASE_URL="${NASH_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

echo "Deleting user ${EMAIL} at ${BASE_URL}..."

RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "${BASE_URL}/api/admin/delete-user" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}" \
  -d "{\"email\": \"${EMAIL}\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "User deleted."
else
  echo "Failed (HTTP ${HTTP_CODE}): ${BODY}"
  exit 1
fi
