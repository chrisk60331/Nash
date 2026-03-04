#!/usr/bin/env bash
# =============================================================================
# Find a deleted user's Backboard assistant by email or user ID.
#
# Searches Backboard assistants named "librechat-user-{userId}" and the auth
# assistant's memory entries to cross-reference email ↔ userId ↔ assistantId.
#
# Usage:
#   ./scripts/find-user-assistant.sh chris@backboard.io
#   ./scripts/find-user-assistant.sh <userId>
#   ./scripts/find-user-assistant.sh --list          # list all user assistants
#
# Env vars:
#   BACKBOARD_API_KEY  — required
# =============================================================================
set -euo pipefail

BB_API="https://app.backboard.io/api"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"

QUERY=$1
skip=0

while true; do
  echo "Fetching page $skip"
  page=$(curl --request GET --url "https://app.backboard.io/api/assistants?skip=${skip}&limit=100"\
   --header "X-API-Key: ${BB_KEY}" -s )

  rows=$(echo "$page" | wc -L)
  echo "Searching Rows: $rows for ${QUERY}"
  if [ $rows -eq 2 ]; then
    break
  fi
  echo "$page" | jq '.[].name'

  skip=$((skip + 100))

done