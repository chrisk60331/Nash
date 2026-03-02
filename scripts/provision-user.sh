#!/usr/bin/env bash
# =============================================================================
# Provision a new Nash user
#
# Usage:
#   ./scripts/provision-user.sh <email> <password> [name] [role]
#   ./scripts/provision-user.sh nash@test.com MyPassword123
#   ./scripts/provision-user.sh admin@co.com SecurePass123 "Admin User" ADMIN
#
# Env vars:
#   NASH_URL             — base URL (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <email> <password> [name] [role]"
  echo "  role: USER (default) or ADMIN"
  exit 1
fi

EMAIL="$1"
PASSWORD="$2"
NAME="${3:-}"
ROLE="${4:-USER}"
BASE_URL="${NASH_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

echo "Provisioning user ${EMAIL} (role: ${ROLE}) at ${BASE_URL}..."

BODY="{\"email\": \"${EMAIL}\", \"password\": \"${PASSWORD}\", \"role\": \"${ROLE}\""
if [ -n "$NAME" ]; then
  BODY="${BODY}, \"name\": \"${NAME}\""
fi
BODY="${BODY}}"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/admin/provision-user" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}" \
  -d "${BODY}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY_OUT=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "201" ]; then
  echo "User created: ${BODY_OUT}"
else
  echo "Failed (HTTP ${HTTP_CODE}): ${BODY_OUT}"
  exit 1
fi
