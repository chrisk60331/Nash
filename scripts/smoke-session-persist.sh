#!/usr/bin/env bash
# =============================================================================
# Smoke test: Session survives multiple refreshes (simulates page reloads)
#
# Verifies that calling /api/auth/refresh twice in a row succeeds.
# Catches the bug where a new refresh token was generated but never stored,
# causing the second reload to fail with "session not found".
#
# Usage:
#   ./scripts/smoke-session-persist.sh
#   BASE_URL=https://nash.backboard.io ./scripts/smoke-session-persist.sh
#
# Env vars:
#   BASE_URL             — API base (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"

TEST_EMAIL="smoketest-sess-$(date +%s)@test.local"
TEST_PASSWORD="SmokeTest123!"
COOKIE_JAR="$(mktemp)"

FAIL() { printf "\n  FAIL: %s\n" "$*"; CLEANUP; exit 1; }
PASS() { printf "  PASS: %s\n" "$*"; }

CLEANUP() {
  curl -sS -o /dev/null -X DELETE "${BASE_URL}/api/admin/delete-user" \
    -H "Content-Type: application/json" \
    -H "x-admin-secret: ${SECRET}" \
    -d "{\"email\":\"${TEST_EMAIL}\"}" 2>/dev/null || true
  rm -f "${COOKIE_JAR}"
}
trap CLEANUP EXIT

echo "Smoke test: session persistence across multiple reloads"
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

# ── Step 3: Login (captures refresh token cookie) ────────────────────────────
echo "[3/6] Logging in..."
LOGIN_RESP=$(curl -sS -w "\n%{http_code}" -c "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
LOGIN_CODE=$(echo "${LOGIN_RESP}" | tail -1)
LOGIN_BODY=$(echo "${LOGIN_RESP}" | sed '$d')
[[ "${LOGIN_CODE}" == "200" ]] || FAIL "Login returned ${LOGIN_CODE}: ${LOGIN_BODY}"
PASS "Login OK"

# ── Step 4: First refresh (simulates first page reload) ──────────────────────
echo "[4/6] First refresh (reload 1)..."
R1_RESP=$(curl -sS -w "\n%{http_code}" -b "${COOKIE_JAR}" -c "${COOKIE_JAR}" \
  -X POST "${BASE_URL}/api/auth/refresh" \
  -H "Content-Type: application/json")
R1_CODE=$(echo "${R1_RESP}" | tail -1)
R1_BODY=$(echo "${R1_RESP}" | sed '$d')

if [[ "${R1_CODE}" != "200" ]]; then
  FAIL "First refresh returned ${R1_CODE}: ${R1_BODY}"
fi

R1_TOKEN=$(echo "${R1_BODY}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
[[ -n "${R1_TOKEN}" ]] || FAIL "First refresh returned no token: ${R1_BODY}"
PASS "First refresh OK (token ${#R1_TOKEN} chars)"

# ── Step 5: Second refresh (simulates second page reload) ─────────────────────
echo "[5/6] Second refresh (reload 2)..."
R2_RESP=$(curl -sS -w "\n%{http_code}" -b "${COOKIE_JAR}" -c "${COOKIE_JAR}" \
  -X POST "${BASE_URL}/api/auth/refresh" \
  -H "Content-Type: application/json")
R2_CODE=$(echo "${R2_RESP}" | tail -1)
R2_BODY=$(echo "${R2_RESP}" | sed '$d')

if [[ "${R2_CODE}" != "200" ]]; then
  FAIL "Second refresh returned ${R2_CODE}: ${R2_BODY}"
fi

R2_TOKEN=$(echo "${R2_BODY}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
[[ -n "${R2_TOKEN}" ]] || FAIL "Second refresh returned no token: ${R2_BODY}"
PASS "Second refresh OK (token ${#R2_TOKEN} chars)"

# ── Step 6: Third refresh (bonus round) ──────────────────────────────────────
echo "[6/6] Third refresh (reload 3)..."
R3_RESP=$(curl -sS -w "\n%{http_code}" -b "${COOKIE_JAR}" -c "${COOKIE_JAR}" \
  -X POST "${BASE_URL}/api/auth/refresh" \
  -H "Content-Type: application/json")
R3_CODE=$(echo "${R3_RESP}" | tail -1)
R3_BODY=$(echo "${R3_RESP}" | sed '$d')

if [[ "${R3_CODE}" != "200" ]]; then
  FAIL "Third refresh returned ${R3_CODE}: ${R3_BODY}"
fi

R3_TOKEN=$(echo "${R3_BODY}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
[[ -n "${R3_TOKEN}" ]] || FAIL "Third refresh returned no token: ${R3_BODY}"
PASS "Third refresh OK (token ${#R3_TOKEN} chars)"

echo ""
echo "All checks passed. Sessions survive multiple page reloads."
