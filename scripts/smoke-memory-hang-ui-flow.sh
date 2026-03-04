#!/usr/bin/env bash
# =============================================================================
# Smoke test: Memory + hang — replicates actual user flow
#
# Uses the same path as the web UI:
# 1. Login
# 2. POST /api/agents/chat/OpenAI (streaming flow)
# 3. GET /api/agents/chat/stream/:streamId (SSE)
# 4. New thread, repeat — this is where the hang occurs
#
# Reproduces:
# - Thread 1: Send fact, AI confirms
# - Thread 2: Ask about preference → HANG (forever blinking)
# - Reload: thread gone, memory not persisted
#
# Usage:
#   SMOKE_TEST_EMAIL=you@example.com SMOKE_TEST_PASSWORD=secret ./scripts/smoke-memory-hang-ui-flow.sh
#
# Env vars:
#   BASE_URL              — API base (default: http://localhost:3080)
#   SMOKE_TEST_EMAIL      — Login email (required)
#   SMOKE_TEST_PASSWORD   — Login password (required)
#   SMOKE_TEST_ENDPOINT   — Endpoint name from config (default: OpenAI)
#   SMOKE_TEST_MODEL      — Model to use (default: openai/gpt-4o)
#   CURL_TIMEOUT          — Seconds for thread 2 stream (default: 90)
#   SMOKE_DEBUG           — If set, dump full stream on failure
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
TIMEOUT="${CURL_TIMEOUT:-90}"
COOKIE_JAR="$(mktemp)"
SSE_OUT="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}" "${SSE_OUT}"' EXIT

FAIL() { echo "FAIL: $*"; exit 1; }
PASS() { echo "PASS: $*"; }

# Endpoint from librechat.yaml custom config (first custom = OpenAI)
ENDPOINT="${SMOKE_TEST_ENDPOINT:-OpenAI}"
MODEL="${SMOKE_TEST_MODEL:-openai/gpt-4o}"

echo "Smoke test: memory + hang (UI flow)"
echo "Target: ${BASE_URL}"
echo "Endpoint: ${ENDPOINT}, Model: ${MODEL}"
echo ""

# Require credentials — agents/chat needs auth
if [[ -z "${SMOKE_TEST_EMAIL:-}" || -z "${SMOKE_TEST_PASSWORD:-}" ]]; then
  FAIL "Set SMOKE_TEST_EMAIL and SMOKE_TEST_PASSWORD (required for agents/chat)"
fi

# Escape for JSON string (backslash and double-quote)
json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

# Browser User-Agent (uaParser rejects curl's default)
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Step 1: Login
echo "[1/6] Logging in..."
EMAIL_ESC=$(json_escape "${SMOKE_TEST_EMAIL}")
PASS_ESC=$(json_escape "${SMOKE_TEST_PASSWORD}")
LOGIN_RESP=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -H "User-Agent: ${UA}" \
  -d "{\"email\":\"${EMAIL_ESC}\",\"password\":\"${PASS_ESC}\"}")
TOKEN=$(echo "${LOGIN_RESP}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)
if [[ -z "${TOKEN}" ]]; then
  FAIL "Login failed: ${LOGIN_RESP}"
fi
PASS "Login OK"

# Build minimal payload matching createPayload + AgentController expectations
# conversationId: null = new thread; parentMessageId: NO_PARENT for first message
build_payload() {
  local text="$1"
  local conv_id="${2:-null}"
  local parent_id="${3:-00000000-0000-0000-0000-000000000000}"
  local msg_id="${4:-$(date +%s)-msg-$RANDOM}"
  local text_esc
  text_esc=$(json_escape "${text}")

  cat << EOF
{
  "text": "${text_esc}",
  "conversationId": ${conv_id},
  "endpoint": "${ENDPOINT}",
  "endpointType": "openAI",
  "model": "${MODEL}",
  "parentMessageId": "${parent_id}",
  "userMessage": {
    "messageId": "${msg_id}",
    "text": "${text_esc}",
    "sender": "User",
    "parentMessageId": "${parent_id}",
    "conversationId": ${conv_id},
    "isCreatedByUser": true
  }
}
EOF
}

# Start chat (POST), get streamId; returns empty on failure
start_chat() {
  local payload="$1"
  local resp
  resp=$(curl -sS -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/agents/chat/${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -H "User-Agent: ${UA}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "${payload}")

  if echo "${resp}" | grep -q '"streamId"'; then
    echo "${resp}" | sed -n 's/.*"streamId":"\([^"]*\)".*/\1/p'
  else
    echo ""
  fi
}

# Extract response text from final event (responseMessage.text or content parts)
extract_response_text() {
  local final_json="$1"
  local text
  text=$(echo "${final_json}" | sed -n 's/.*"text":"\([^"]*\)".*/\1/p' | head -1 | sed 's/\\n/\n/g')
  if [[ -n "${text}" ]] && [[ "${#text}" -gt 2 ]]; then
    echo "${text}"
    return
  fi
  # Fallback: accumulate "value" from content parts
  echo "${final_json}" | grep -o '"value":"[^"]*"' | sed 's/"value":"\(.*\)"/\1/g' | tr -d '\n' | head -c 2000
}

# Step 2: Thread 1 — new conversation, send fact
echo ""
echo "[2/6] Thread 1: New thread, sending fact (I prefer red pens)..."
PAYLOAD1=$(build_payload "I prefer red pens. Please remember this.")
STREAM1=$(start_chat "${PAYLOAD1}")

if [[ -z "${STREAM1}" ]]; then
  echo "Response from start_chat:"
  curl -sS -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/agents/chat/${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -H "User-Agent: ${UA}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "${PAYLOAD1}" | head -c 500
  FAIL "Thread 1: Failed to get streamId (check endpoint/model config)"
fi
PASS "Thread 1: Got streamId ${STREAM1:0:8}..."

# Brief delay so job is ready before we subscribe
sleep 1

# Consume stream (60s timeout for thread 1)
echo "Consuming stream..."
> "${SSE_OUT}"
FINAL1=""
GOT_ERROR=""
while IFS= read -r line; do
  if [[ "${line}" =~ ^event:\ error ]]; then
    GOT_ERROR=1
  elif [[ "${line}" =~ ^data:\ (.*) ]]; then
    FINAL1="${BASH_REMATCH[1]}"
    if echo "${FINAL1}" | grep -qE '"final"\s*:\s*true'; then
      break
    fi
    if [[ -n "${GOT_ERROR}" ]]; then
      break
    fi
  fi
done < <(curl -sS -N -m 60 -b "${COOKIE_JAR}" \
  -H "User-Agent: ${UA}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: text/event-stream" \
  "${BASE_URL}/api/agents/chat/stream/${STREAM1}" 2>/dev/null | tee "${SSE_OUT}")

if [[ -n "${GOT_ERROR}" ]]; then
  echo "Stream error event received:"
  grep -A1 'event: error' "${SSE_OUT}" 2>/dev/null || true
  FAIL "Thread 1: Stream reported error"
fi
if [[ -z "${FINAL1}" ]] || ! echo "${FINAL1}" | grep -q '"final"'; then
  echo "Stream output (last 1200 chars):"
  tail -c 1200 "${SSE_OUT}" 2>/dev/null || echo "(none)"
  if [[ -n "${SMOKE_DEBUG:-}" ]]; then
    echo "--- Full stream (SMOKE_DEBUG=1) ---"
    cat "${SSE_OUT}" 2>/dev/null || true
    echo "---"
  fi
  FAIL "Thread 1: No final event received"
fi
PASS "Thread 1: Stream complete"

# Allow memory to be flushed to Backboard before thread 2
sleep 3

# Step 3: Thread 2 — NEW thread (conversationId: null), ask about preference
echo ""
echo "[3/6] Thread 2: New thread, asking about pen preference (timeout ${TIMEOUT}s)..."
PAYLOAD2=$(build_payload "What is my pen preference? Remember from our prior conversation.")
STREAM2=$(start_chat "${PAYLOAD2}")

if [[ -z "${STREAM2}" ]]; then
  FAIL "Thread 2: Failed to get streamId"
fi
PASS "Thread 2: Got streamId ${STREAM2:0:8}..."

# Consume stream with timeout — THIS IS WHERE HANG OCCURS
> "${SSE_OUT}"
set +e
curl -sS -N -m "${TIMEOUT}" -b "${COOKIE_JAR}" \
  -H "User-Agent: ${UA}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: text/event-stream" \
  "${BASE_URL}/api/agents/chat/stream/${STREAM2}" >> "${SSE_OUT}" 2>/dev/null
CURL_EXIT=$?
set -e

# curl -m exits 28 on timeout
if [[ "${CURL_EXIT}" -eq 28 ]]; then
  FAIL "Thread 2: HANG DETECTED (timed out after ${TIMEOUT}s) — repro confirmed"
fi

FINAL2=$(grep 'data: ' "${SSE_OUT}" 2>/dev/null | grep -E '"final"\s*:\s*true' | tail -1 | sed 's/^data: //')
if [[ -z "${FINAL2}" ]] || ! echo "${FINAL2}" | grep -q '"final"'; then
  echo "Stream output (last 500 chars):"
  tail -c 500 "${SSE_OUT}" 2>/dev/null || echo "(none)"
  FAIL "Thread 2: No final event (exit ${CURL_EXIT})"
fi
PASS "Thread 2: Stream complete (no hang)"

# Step 4: Check memory (non-fatal — continue to show full repro)
echo ""
echo "[4/6] Checking if AI remembered (looking for 'red')..."
RESPONSE2=$(extract_response_text "${FINAL2}")
MEMORY_OK=0
if echo "${RESPONSE2}" | grep -qi 'red'; then
  PASS "Memory retained: response mentions red"
  MEMORY_OK=1
else
  echo "Response: ${RESPONSE2:0:300}..."
  echo "FAIL: Memory NOT retained: response does not mention 'red'"
fi

# Step 5: List convos
echo ""
echo "[5/6] Listing conversations..."
CONVOS=$(curl -sS -b "${COOKIE_JAR}" -X GET "${BASE_URL}/api/convos?limit=100" \
  -H "User-Agent: ${UA}" \
  -H "Authorization: Bearer ${TOKEN}")
CONVO_COUNT=$(echo "${CONVOS}" | grep -o '"conversationId"' | wc -l | tr -d ' ')
echo "Found ${CONVO_COUNT} conversation(s)"

# Step 6: Summary
echo ""
echo "[6/6] Summary"
echo "---"
if [[ "${MEMORY_OK}" -eq 1 ]]; then
  PASS "Memory + hang smoke test (UI flow) complete."
  echo "  - Thread 1: fact sent, stream completed"
  echo "  - Thread 2: no hang, memory recalled"
else
  echo "Stream flow: PASS (threads 1 & 2 completed)"
  echo "Memory: FAIL (not retained)"
  echo ""
  echo "If you see HANG DETECTED, the repro is confirmed."
  echo "If memory not retained, check Backboard flush (4096 byte limit)."
  exit 1
fi
echo ""
echo "If you see HANG DETECTED, the repro is confirmed."
echo "If 403 on agents/chat, check agents config or use OpenAI endpoint from your librechat.yaml"
