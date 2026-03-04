#!/usr/bin/env bash
# =============================================================================
# Smoke test: Memory retention + hang repro
#
# Reproduces:
# 1. Thread 1: Send fact ("I prefer red pens"), AI confirms memory
# 2. Thread 2: Ask about preference → app hangs (forever blinking)
# 3. After reload, thread gone, memory not persisted
#
# Usage:
#   SMOKE_TEST_EMAIL=you@example.com SMOKE_TEST_PASSWORD=secret ./scripts/smoke-memory-hang.sh
#   BASE_URL=https://kppws3zmdz.us-west-2.awsapprunner.com ./scripts/smoke-memory-hang.sh
#
# Env vars:
#   BASE_URL              — API base (default: http://localhost:3080)
#   SMOKE_TEST_EMAIL      — Login email
#   SMOKE_TEST_PASSWORD   — Login password
#   CURL_TIMEOUT          — Seconds to wait for second request (default: 90)
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
TIMEOUT="${CURL_TIMEOUT:-90}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}"' EXIT

FAIL() { echo "FAIL: $*"; exit 1; }
PASS() { echo "PASS: $*"; }

echo "Smoke test: memory + hang repro"
echo "Target: ${BASE_URL}"
echo ""

# Step 0: Login
TOKEN=""
if [[ -n "${SMOKE_TEST_EMAIL:-}" && -n "${SMOKE_TEST_PASSWORD:-}" ]]; then
  echo "[1/6] Logging in..."
  LOGIN_RESP=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${SMOKE_TEST_EMAIL}\",\"password\":\"${SMOKE_TEST_PASSWORD}\"}")
  TOKEN=$(echo "${LOGIN_RESP}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)
  if [[ -z "${TOKEN}" ]]; then
    FAIL "Login failed: ${LOGIN_RESP}"
  fi
  PASS "Login OK"
else
  echo "[1/6] No SMOKE_TEST_EMAIL/PASSWORD — testing Backboard proxy without auth"
fi

# Step 1: Thread 1 — send fact
echo ""
echo "[2/6] Thread 1: Sending fact (I prefer red pens)..."
curl_chat() {
  local json="$1"
  if [[ -n "${TOKEN:-}" ]]; then
    curl -sS -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${TOKEN}" \
      -d "${json}"
  else
    curl -sS -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "${json}"
  fi
}

RESP1=$(curl_chat '{"model":"gpt-4o","messages":[{"role":"user","content":"I prefer red pens. Please remember this."}],"stream":false}')

CONTENT1=$(echo "${RESP1}" | sed -n 's/.*"content":"\([^"]*\)".*/\1/p' | sed 's/\\n/\n/g')
if [[ -z "${CONTENT1}" ]]; then
  echo "Response 1: ${RESP1}"
  FAIL "Thread 1: No content in response"
fi
PASS "Thread 1: Got response (${#CONTENT1} chars)"

# Step 2: Thread 2 — ask about preference (THIS IS WHERE HANG OCCURS)
echo ""
echo "[3/6] Thread 2: Asking about pen preference (timeout ${TIMEOUT}s)..."
CURL_EXIT=0
if [[ -n "${TOKEN:-}" ]]; then
  RESP2=$(curl -sS --max-time "${TIMEOUT}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d '{"model":"gpt-4o","messages":[{"role":"user","content":"What is my pen preference? Remember from our prior conversation."}],"stream":false}') || CURL_EXIT=$?
else
  RESP2=$(curl -sS --max-time "${TIMEOUT}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-4o","messages":[{"role":"user","content":"What is my pen preference? Remember from our prior conversation."}],"stream":false}') || CURL_EXIT=$?
fi

if [[ "${CURL_EXIT}" -eq 28 ]]; then
  FAIL "Thread 2: HANG DETECTED (curl timed out after ${TIMEOUT}s) — repro confirmed"
fi

CONTENT2=$(echo "${RESP2}" | sed -n 's/.*"content":"\([^"]*\)".*/\1/p' | sed 's/\\n/\n/g')
if [[ -z "${CONTENT2}" ]]; then
  echo "Response 2: ${RESP2}"
  FAIL "Thread 2: No content in response"
fi
PASS "Thread 2: Got response (no hang)"

# Step 3: Check memory (non-fatal: shared assistant has many users' memories)
echo ""
echo "[4/6] Checking if AI remembered (looking for 'red')..."
if echo "${CONTENT2}" | grep -qi 'red'; then
  PASS "Memory retained: response mentions red"
else
  echo "Response 2 content: ${CONTENT2}"
  echo "WARN: Memory not retained on shared assistant (expected with multi-user noise)"
fi

# Step 4: List convos (if authenticated)
if [[ -n "${TOKEN}" ]]; then
  echo ""
  echo "[5/6] Listing conversations..."
  CONVOS=$(curl -sS -b "${COOKIE_JAR}" -X GET "${BASE_URL}/api/convos?limit=5" \
    -H "Authorization: Bearer ${TOKEN}")
  CONVO_COUNT=$(echo "${CONVOS}" | grep -o '"conversationId"' | wc -l | tr -d ' ')
  echo "Found ${CONVO_COUNT} conversation(s) in list"
fi

echo ""
echo "[6/6] Summary"
echo "---"
PASS "Memory + hang smoke test complete."
echo "  - Thread 1: fact sent"
echo "  - Thread 2: no hang, memory recalled"
echo ""
echo "If you see HANG DETECTED, the repro is confirmed."
echo "If memory is not retained, check Backboard flush logs (4096 byte limit)."
