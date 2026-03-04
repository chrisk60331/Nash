#!/usr/bin/env bash
# =============================================================================
# Reattach an orphaned Backboard assistant to a (re-created) user.
#
# Step 1: Lists current users from the auth store
# Step 2: Renames the orphaned assistant to "librechat-user-{newUserId}"
#
# Usage:
#   ./scripts/reattach-user-assistant.sh                          # interactive: list users, then prompt
#   ./scripts/reattach-user-assistant.sh --list                   # just list users
#   ./scripts/reattach-user-assistant.sh <assistant_id> <user_id> # direct reattach
#
# Env vars:
#   BACKBOARD_API_KEY  — required
# =============================================================================
set -euo pipefail

BB_API="https://app.backboard.io/api"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"
PAGE_SIZE=500

bb_get() {
  curl -sS --header "X-API-Key: ${BB_KEY}" "$1"
}

bb_put() {
  curl -sS --header "X-API-Key: ${BB_KEY}" \
    --header "Content-Type: application/json" \
    --request PUT \
    --data "$2" \
    "$1"
}

# ─── Find the auth assistant ─────────────────────────────────────────────────
find_auth_assistant() {
  local skip=0
  while true; do
    local page
    page=$(bb_get "${BB_API}/assistants?skip=${skip}&limit=${PAGE_SIZE}")
    local aid
    aid=$(echo "${page}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('assistants', data.get('data', []))
for a in items:
    if a.get('name') == 'librechat-auth':
        print(a.get('assistant_id', a.get('id', '')))
        sys.exit(0)
count = len(items)
if count == 0:
    sys.exit(1)
" 2>/dev/null) && { echo "${aid}"; return 0; }

    local count
    count=$(echo "${page}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('assistants', data.get('data', []))
print(len(items))
")
    if [[ "${count}" -lt "${PAGE_SIZE}" ]]; then
      break
    fi
    skip=$((skip + PAGE_SIZE))
  done
  echo ""
}

# ─── List users from auth assistant ──────────────────────────────────────────
list_users() {
  local auth_aid="$1"
  echo "Fetching users from auth assistant ${auth_aid}..."
  local memories
  memories=$(bb_get "${BB_API}/assistants/${auth_aid}/memories")

  echo "${memories}" | python3 -c "
import sys, json

data = json.load(sys.stdin)
memories = data if isinstance(data, list) else data.get('memories', data.get('data', []))

users = []
for m in memories:
    meta = m.get('metadata', {})
    if meta.get('type') != 'librechat_user':
        continue
    try:
        content = json.loads(m.get('content', '{}'))
    except:
        continue
    users.append({
        'id': content.get('_id', content.get('id', meta.get('entryId', '???'))),
        'email': content.get('email', '???'),
        'name': content.get('name', ''),
        'provider': content.get('provider', ''),
        'role': content.get('role', ''),
        'created': content.get('createdAt', ''),
    })

users.sort(key=lambda u: u.get('created', ''), reverse=True)

print(f'Found {len(users)} user(s):')
print()
print(f'{\"ID\":<40} {\"EMAIL\":<35} {\"NAME\":<20} {\"PROVIDER\":<10} {\"ROLE\":<8}')
print('-' * 115)
for u in users:
    uid = u['id'][:38] if len(u['id']) > 38 else u['id']
    print(f'{uid:<40} {u[\"email\"]:<35} {u[\"name\"]:<20} {u[\"provider\"]:<10} {u[\"role\"]:<8}')
"
}

# ─── Reattach: rename assistant ──────────────────────────────────────────────
reattach() {
  local assistant_id="$1"
  local new_user_id="$2"
  local new_name="librechat-user-${new_user_id}"

  echo ""
  echo "Renaming assistant ${assistant_id} → ${new_name}"

  local resp
  resp=$(bb_put "${BB_API}/assistants/${assistant_id}" \
    "{\"name\":\"${new_name}\"}")

  local updated_name
  updated_name=$(echo "${resp}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('name', 'ERROR'))
" 2>/dev/null || echo "ERROR")

  if [[ "${updated_name}" == "${new_name}" ]]; then
    echo "OK: Assistant ${assistant_id} is now named '${new_name}'"
    echo ""
    echo "The user will pick up this assistant on their next request."
    echo "If the server is running, the in-memory cache will expire within 30s."
  else
    echo "WARN: Expected name '${new_name}' but got '${updated_name}'"
    echo "Full response:"
    echo "${resp}" | python3 -m json.tool 2>/dev/null || echo "${resp}"
  fi
}

# ─── Also check for duplicate assistants and clean up name conflicts ─────────
check_existing_assistant() {
  local new_user_id="$1"
  local target_name="librechat-user-${new_user_id}"
  local skip=0

  while true; do
    local page
    page=$(bb_get "${BB_API}/assistants?skip=${skip}&limit=${PAGE_SIZE}")
    local found
    found=$(echo "${page}" | python3 -c "
import sys, json
target = '${target_name}'
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('assistants', data.get('data', []))
matches = [a for a in items if a.get('name') == target]
for m in matches:
    print(m.get('assistant_id', m.get('id', '')))
" 2>/dev/null || true)

    if [[ -n "${found}" ]]; then
      echo "WARNING: An assistant named '${target_name}' already exists:"
      echo "  ${found}"
      echo ""
      echo "This will be an empty assistant created when the user first logged in."
      echo "It needs to be renamed before we can reattach the old one."
      echo ""
      read -rp "Rename the existing empty assistant to '${target_name}-replaced-$(date +%s)'? [y/N] " confirm
      if [[ "${confirm}" =~ ^[Yy] ]]; then
        local replacement_name="${target_name}-replaced-$(date +%s)"
        bb_put "${BB_API}/assistants/${found}" "{\"name\":\"${replacement_name}\"}" > /dev/null
        echo "OK: Renamed existing assistant to '${replacement_name}'"
      else
        echo "Aborted. Resolve the naming conflict manually."
        exit 1
      fi
    fi

    local count
    count=$(echo "${page}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('assistants', data.get('data', []))
print(len(items))
")
    if [[ "${count}" -lt "${PAGE_SIZE}" ]]; then
      break
    fi
    skip=$((skip + PAGE_SIZE))
  done
}

# ─── Main ────────────────────────────────────────────────────────────────────
MODE="${1:---interactive}"

echo "Finding auth assistant..."
AUTH_AID=$(find_auth_assistant)
if [[ -z "${AUTH_AID}" ]]; then
  echo "ERROR: Could not find librechat-auth assistant"
  exit 1
fi
echo "Auth assistant: ${AUTH_AID}"
echo ""

if [[ "${MODE}" == "--list" ]]; then
  list_users "${AUTH_AID}"
  exit 0
fi

if [[ "${MODE}" != "--interactive" && -n "${2:-}" ]]; then
  ASSISTANT_ID="${MODE}"
  USER_ID="$2"
  check_existing_assistant "${USER_ID}"
  reattach "${ASSISTANT_ID}" "${USER_ID}"
  exit 0
fi

# Interactive mode
list_users "${AUTH_AID}"
echo ""
read -rp "Enter the ORPHANED assistant_id (from find-user-assistant.sh): " ASSISTANT_ID
read -rp "Enter the target user ID (from list above): " USER_ID

if [[ -z "${ASSISTANT_ID}" || -z "${USER_ID}" ]]; then
  echo "Both assistant_id and user_id are required."
  exit 1
fi

check_existing_assistant "${USER_ID}"
reattach "${ASSISTANT_ID}" "${USER_ID}"
