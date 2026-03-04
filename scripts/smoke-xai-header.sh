#!/usr/bin/env bash
# =============================================================================
# Smoke test: xAI models — x-backboard-user-id header propagation
#
# Reproduces the error:
#   [Backboard Proxy] Rejecting request: no x-backboard-user-id header
#   Missing user identity — cannot route to assistant
#
# Tests THREE layers:
#   1. Direct proxy call WITHOUT header → must fail (400, confirms guard works)
#   2. Direct proxy call WITH header → must succeed (200 or upstream error, NOT 400)
#   3. Through-the-app: login, send xAI chat via /api/agents/chat/xAI SSE stream
#      → must NOT get "Missing user identity" error (header must propagate)
#
# Usage:
#   ./scripts/smoke-xai-header.sh
#   BASE_URL=https://nash.backboard.io ./scripts/smoke-xai-header.sh
#
# Env vars:
#   BASE_URL             — API base (default: http://localhost:3080)
#   ADMIN_RESET_SECRET   — must match the server's ADMIN_RESET_SECRET
#   CURL_TIMEOUT         — seconds to wait per request (default: 60)
#   XAI_MODEL            — model to test (default: xai/grok-3-mini)
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
SECRET="${ADMIN_RESET_SECRET:?Set ADMIN_RESET_SECRET to match the server}"
TIMEOUT="${CURL_TIMEOUT:-60}"
XAI_MODEL="${XAI_MODEL:-xai/grok-3-mini}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"

TEST_EMAIL="smoketest-xai-$(date +%s)@test.local"
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

echo "Smoke test: xAI x-backboard-user-id header propagation"
echo "Target: ${BASE_URL}"
echo "Model:  ${XAI_MODEL}"
echo ""

# ── Step 1: Health check ────────────────────────────────────────────────────
echo "[1/5] Health check..."
STATUS=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "${BASE_URL}/health")
[[ "${STATUS}" == "200" ]] || FAIL "Health check returned ${STATUS}"
PASS "Health OK"

# ── Step 2: Direct proxy — WITHOUT header (must fail with 400) ─────────────
echo "[2/5] Direct proxy call WITHOUT x-backboard-user-id header..."
NO_HDR_RESP=$(curl -sS -w "\n%{http_code}" --max-time "${TIMEOUT}" \
  -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${XAI_MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello.\"}],\"stream\":false}")

NO_HDR_CODE=$(echo "${NO_HDR_RESP}" | tail -1)
NO_HDR_BODY=$(echo "${NO_HDR_RESP}" | sed '$d')

if [[ "${NO_HDR_CODE}" == "400" ]]; then
  PASS "Proxy correctly rejects missing header (400)"
else
  echo "  Response: ${NO_HDR_BODY}"
  FAIL "Expected 400 for missing header, got ${NO_HDR_CODE}"
fi

# ── Step 3: Direct proxy — WITH header (must NOT be 400) ───────────────────
echo "[3/5] Direct proxy call WITH x-backboard-user-id header..."
WITH_HDR_RESP=$(curl -sS -w "\n%{http_code}" --max-time "${TIMEOUT}" \
  -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "x-backboard-user-id: smoke-test-user" \
  -H "x-backboard-user-name: Smoke Tester" \
  -d "{\"model\":\"${XAI_MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one word.\"}],\"stream\":false}")

WITH_HDR_CODE=$(echo "${WITH_HDR_RESP}" | tail -1)
WITH_HDR_BODY=$(echo "${WITH_HDR_RESP}" | sed '$d')

if [[ "${WITH_HDR_CODE}" == "400" ]] && echo "${WITH_HDR_BODY}" | grep -qi "Missing user identity"; then
  FAIL "Header not reaching proxy — 'Missing user identity' returned despite sending header"
elif [[ "${WITH_HDR_CODE}" == "200" ]]; then
  PASS "Direct proxy with header returned 200 (fully working)"
else
  echo "  INFO: Proxy returned ${WITH_HDR_CODE} (upstream issue, not header issue)"
  PASS "Header accepted by proxy (status ${WITH_HDR_CODE})"
fi

# ── Step 4: Provision test user + login ─────────────────────────────────────
echo "[4/5] Creating test user and logging in..."
PROV_RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/api/admin/provision-user" \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: ${SECRET}" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"name\":\"Smoke Tester\"}")
PROV_CODE=$(echo "${PROV_RESP}" | tail -1)
PROV_BODY=$(echo "${PROV_RESP}" | sed '$d')
[[ "${PROV_CODE}" == "201" ]] || FAIL "Provision user returned ${PROV_CODE}: ${PROV_BODY}"

LOGIN_RESP=$(curl -sS -w "\n%{http_code}" -c "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
LOGIN_CODE=$(echo "${LOGIN_RESP}" | tail -1)
LOGIN_BODY=$(echo "${LOGIN_RESP}" | sed '$d')
[[ "${LOGIN_CODE}" == "200" ]] || FAIL "Login returned ${LOGIN_CODE}: ${LOGIN_BODY}"

TOKEN=$(echo "${LOGIN_BODY}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)
[[ -n "${TOKEN}" ]] || FAIL "Login returned no token: ${LOGIN_BODY}"
PASS "User created and logged in"

# ── Step 5: Through-the-app — agents/chat endpoint with xAI model ──────────
echo "[5/5] Sending xAI chat via /api/agents/chat/xAI (timeout ${TIMEOUT}s)..."

CHAT_BODY=$(cat <<ENDJSON
{
  "endpoint": "xAI",
  "endpointType": "custom",
  "text": "Say hello in exactly one word.",
  "model": "${XAI_MODEL}",
  "conversationId": "new",
  "parentMessageId": "00000000-0000-0000-0000-000000000000",
  "isContinued": false,
  "isEdited": false
}
ENDJSON
)

# Step 5a: Create the generation job
CURL_EXIT=0
CREATE_RESP=$(curl -sS --max-time "${TIMEOUT}" \
  -b "${COOKIE_JAR}" \
  -X POST "${BASE_URL}/api/agents/chat/xAI" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "User-Agent: ${UA}" \
  -d "${CHAT_BODY}" 2>&1) || CURL_EXIT=$?

if [[ "${CURL_EXIT}" -eq 28 ]]; then
  FAIL "HANG on job creation — curl timed out after ${TIMEOUT}s"
fi

STREAM_ID=$(echo "${CREATE_RESP}" | sed -n 's/.*"streamId":"\([^"]*\)".*/\1/p')
if [[ -z "${STREAM_ID}" ]]; then
  echo "  Response: ${CREATE_RESP:0:500}"
  if echo "${CREATE_RESP}" | grep -qi "Missing user identity"; then
    FAIL "REPRO CONFIRMED — 'Missing user identity' in job creation response"
  fi
  FAIL "No streamId in response"
fi

echo "  Job created: ${STREAM_ID}"

# Step 5b: Subscribe to the SSE stream
CURL_EXIT=0
STREAM_RESP=$(curl -sS -N --max-time "${TIMEOUT}" \
  -b "${COOKIE_JAR}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "User-Agent: ${UA}" \
  "${BASE_URL}/api/agents/chat/stream/${STREAM_ID}" 2>&1) || CURL_EXIT=$?

if [[ "${CURL_EXIT}" -eq 28 ]]; then
  echo "  Stream so far: ${STREAM_RESP:0:500}"
  FAIL "HANG DETECTED — stream timed out after ${TIMEOUT}s"
fi

if echo "${STREAM_RESP}" | grep -qi "Missing user identity"; then
  echo "  Stream: ${STREAM_RESP:0:500}"
  FAIL "REPRO CONFIRMED — 'Missing user identity' in stream response"
fi

# Check for the final message with content
if echo "${STREAM_RESP}" | grep -q '"final":true'; then
  CONTENT=$(echo "${STREAM_RESP}" | grep 'on_message_delta' | sed -n 's/.*"text":"\([^"]*\)".*/\1/p' | tr -d '\n')
  PASS "xAI chat completed (content: '${CONTENT:0:100}')"
elif echo "${STREAM_RESP}" | grep -qi '"type":"error"'; then
  ERROR_MSG=$(echo "${STREAM_RESP}" | grep -i error | head -3)
  echo "  Error in stream: ${ERROR_MSG}"
  FAIL "xAI chat returned an error in stream"
else
  echo "  Stream (first 500 chars): ${STREAM_RESP:0:500}"
  FAIL "Unexpected stream response (no final message)"
fi

echo ""
echo "──────────────────────────────────────────────────"
echo "All checks passed."
echo "  - Proxy rejects requests without x-backboard-user-id header (400)"
echo "  - Proxy accepts requests with x-backboard-user-id header"
echo "  - Through-the-app xAI chat completes without 'Missing user identity' error"
echo ""
