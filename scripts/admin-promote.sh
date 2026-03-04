#!/usr/bin/env bash
# =============================================================================
# Promote (or demote) a user to ADMIN (or USER) role.
#
# Usage:
#   ./scripts/admin-promote.sh user@example.com
#   ./scripts/admin-promote.sh user@example.com USER        # demote
#   BASE_URL=https://nash.backboard.io ./scripts/admin-promote.sh user@example.com
#
# Env vars:
#   BASE_URL             — API base (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

EMAIL="${1:?Usage: $0 <email> [ADMIN|USER]}"
ROLE="${2:-ADMIN}"

echo "Promoting user to ${ROLE}..."
echo "  Target: ${BASE_URL}"
echo "  Email:  ${EMAIL}"
echo ""

RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/api/admin/set-role" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}" \
  -d "{\"email\":\"${EMAIL}\",\"role\":\"${ROLE}\"}")

CODE=$(echo "${RESP}" | tail -1)
BODY=$(echo "${RESP}" | sed '$d')

if [[ "${CODE}" != "200" ]]; then
  echo "FAIL: POST /api/admin/set-role returned ${CODE}"
  echo "Response: ${BODY}"
  exit 1
fi

echo "OK: ${EMAIL} is now ${ROLE}"
echo "Response: ${BODY}"
