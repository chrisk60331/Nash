#!/usr/bin/env bash
# =============================================================================
# Smoke test: Memories survive page reload
#
# Verifies that a memory created via the API is returned on a fresh GET
# (simulating a page reload). This catches the bug where writes went to the
# shared Backboard assistant but reads came from the per-user assistant.
#
# Usage:
#   ./scripts/smoke-memory-persist.sh
#   BASE_URL=https://nash.backboard.io ./scripts/smoke-memory-persist.sh
#
# Env vars:
#   BASE_URL             — API base (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

TEST_EMAIL="smoketest-mem-$(date +%s)@test.local"
TEST_PASSWORD="SmokeTest123!"
MEMORY_KEY="smoke_pen_color_$(date +%s)"
MEMORY_VALUE="User prefers red pens for writing"

FAIL() { printf "\n  FAIL: %s\n" "$*"; CLEANUP; exit 1; }
PASS() { printf "  PASS: %s\n" "$*"; }

CLEANUP() {
  if [[ -n "${TOKEN:-}" ]]; then
    curl -sS -o /dev/null -X DELETE "${BASE_URL}/api/memories/${MEMORY_KEY}" \
      -H "Authorization: Bearer ${TOKEN}" 2>/dev/null || true
  fi
  curl -sS -o /dev/null -X DELETE "${BASE_URL}/api/admin/delete-user" \
    -H "Content-Type: application/json" \
    -H "x-admin-secret: ${SECRET}" \
    -d "{\"email\":\"${TEST_EMAIL}\"}" 2>/dev/null || true
}
trap CLEANUP EXIT

echo "Smoke test: memory persistence across reload"
echo "Target: ${BASE_URL}"
echo ""

# ── Step 1: Health check ──────────────────────────────────────────────────────
echo "[1/6] Health check..."
STATUS=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/health")
[[ "${STATUS}" == "200" ]] || FAIL "Health check returned ${STATUS}"
PASS "Health OK"

# ── Step 2: Provision test user ───────────────────────────────────────────────
echo "[2/6] Creating test user ${TEST_EMAIL}..."
PROV_RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/api/admin/provision-user" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
PROV_CODE=$(echo "${PROV_RESP}" | tail -1)
PROV_BODY=$(echo "${PROV_RESP}" | sed '$d')
[[ "${PROV_CODE}" == "201" ]] || FAIL "Provision user returned ${PROV_CODE}: ${PROV_BODY}"
PASS "User created"

# ── Step 3: Login ─────────────────────────────────────────────────────────────
echo "[3/6] Logging in..."
LOGIN_RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
LOGIN_CODE=$(echo "${LOGIN_RESP}" | tail -1)
LOGIN_BODY=$(echo "${LOGIN_RESP}" | sed '$d')
[[ "${LOGIN_CODE}" == "200" ]] || FAIL "Login returned ${LOGIN_CODE}: ${LOGIN_BODY}"

TOKEN=$(echo "${LOGIN_BODY}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
[[ -n "${TOKEN}" ]] || FAIL "No token in login response: ${LOGIN_BODY}"
PASS "Login OK (token ${#TOKEN} chars)"

# ── Step 4: Create memory ────────────────────────────────────────────────────
echo "[4/6] Creating memory [${MEMORY_KEY}]..."
CREATE_RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/api/memories" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"key\":\"${MEMORY_KEY}\",\"value\":\"${MEMORY_VALUE}\"}")
CREATE_CODE=$(echo "${CREATE_RESP}" | tail -1)
CREATE_BODY=$(echo "${CREATE_RESP}" | sed '$d')
[[ "${CREATE_CODE}" == "201" ]] || FAIL "Create memory returned ${CREATE_CODE}: ${CREATE_BODY}"
PASS "Memory created"

# ── Step 5: Fetch memories (simulates page reload) ───────────────────────────
echo "[5/6] Fetching all memories (simulating page reload)..."
GET_RESP=$(curl -sS -w "\n%{http_code}" -X GET "${BASE_URL}/api/memories" \
  -H "Authorization: Bearer ${TOKEN}")
GET_CODE=$(echo "${GET_RESP}" | tail -1)
GET_BODY=$(echo "${GET_RESP}" | sed '$d')
[[ "${GET_CODE}" == "200" ]] || FAIL "GET /memories returned ${GET_CODE}: ${GET_BODY}"

if echo "${GET_BODY}" | grep -q "${MEMORY_KEY}"; then
  PASS "Memory found in GET response"
else
  FAIL "Memory key '${MEMORY_KEY}' NOT found in GET /memories response: ${GET_BODY}"
fi

if echo "${GET_BODY}" | grep -q "red pens"; then
  PASS "Memory value matches"
else
  FAIL "Memory value 'red pens' NOT found in GET /memories response: ${GET_BODY}"
fi

# ── Step 6: Delete memory ────────────────────────────────────────────────────
echo "[6/6] Deleting memory..."
DEL_RESP=$(curl -sS -w "\n%{http_code}" -X DELETE \
  "${BASE_URL}/api/memories/${MEMORY_KEY}" \
  -H "Authorization: Bearer ${TOKEN}")
DEL_CODE=$(echo "${DEL_RESP}" | tail -1)
[[ "${DEL_CODE}" == "200" ]] || FAIL "Delete memory returned ${DEL_CODE}"

GET2_RESP=$(curl -sS "${BASE_URL}/api/memories" \
  -H "Authorization: Bearer ${TOKEN}")
if echo "${GET2_RESP}" | grep -q "${MEMORY_KEY}"; then
  FAIL "Memory still present after delete"
else
  PASS "Memory deleted and confirmed gone"
fi

echo ""
echo "All checks passed. Memories persist across simulated page reloads."
