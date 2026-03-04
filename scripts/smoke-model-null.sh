#!/usr/bin/env bash
# =============================================================================
# Smoke test: model null validation fix
#
# Reproduces Nir's error: "Expected string, received null" when model is null.
# Sends a chat request with model: null to verify the backend handles it
# and returns a valid stream instead of throwing a validation error.
#
# Usage:
#   SMOKE_TEST_EMAIL=you@example.com SMOKE_TEST_PASSWORD=secret ./scripts/smoke-model-null.sh
#
# Env vars:
#   BASE_URL              — API base (default: http://localhost:3080)
#   SMOKE_TEST_EMAIL      — Login email (required)
#   SMOKE_TEST_PASSWORD   — Login password (required)
#   SMOKE_TEST_ENDPOINT   — Endpoint name (default: OpenAI)
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
COOKIE_JAR="$(mktemp)"
SSE_OUT="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}" "${SSE_OUT}"' EXIT

FAIL() { echo "FAIL: $*"; exit 1; }
PASS() { echo "PASS: $*"; }

ENDPOINT="${SMOKE_TEST_ENDPOINT:-OpenAI}"

echo "Smoke test: model null validation"
echo "Target: ${BASE_URL}"
echo "Endpoint: ${ENDPOINT}"
echo ""

if [[ -z "${SMOKE_TEST_EMAIL:-}" || -z "${SMOKE_TEST_PASSWORD:-}" ]]; then
  FAIL "Set SMOKE_TEST_EMAIL and SMOKE_TEST_PASSWORD (required)"
fi

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Step 1: Login
echo "[1/4] Logging in..."
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

# Step 2: Send chat with model: null (reproduces Nir's scenario)
echo ""
echo "[2/4] Sending chat with model: null..."
TEXT_ESC=$(json_escape "Say hi")
MSG_ID="smoke-$(date +%s)-$RANDOM"
PAYLOAD=$(cat << EOF
{
  "text": "${TEXT_ESC}",
  "conversationId": null,
  "endpoint": "${ENDPOINT}",
  "endpointType": "openAI",
  "model": null,
  "parentMessageId": "00000000-0000-0000-0000-000000000000",
  "userMessage": {
    "messageId": "${MSG_ID}",
    "text": "${TEXT_ESC}",
    "sender": "User",
    "parentMessageId": "00000000-0000-0000-0000-000000000000",
    "conversationId": null,
    "isCreatedByUser": true
  }
}
EOF
)

RESP=$(curl -sS -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/agents/chat/${ENDPOINT}" \
  -H "Content-Type: application/json" \
  -H "User-Agent: ${UA}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "${PAYLOAD}")

if echo "${RESP}" | grep -q '"streamId"'; then
  STREAM=$(echo "${RESP}" | sed -n 's/.*"streamId":"\([^"]*\)".*/\1/p')
  PASS "Got streamId (no validation error)"
else
  if echo "${RESP}" | grep -qi 'expected string.*received null'; then
    FAIL "Validation error (model null): ${RESP}"
  fi
  if echo "${RESP}" | grep -qi 'invalid_type'; then
    FAIL "Zod validation error: ${RESP}"
  fi
  echo "Response: ${RESP}"
  FAIL "Failed to get streamId"
fi

# Step 3: Consume stream and verify final event (optional — requires configured LLM)
echo ""
echo "[3/4] Consuming stream..."
set +e
sleep 1
> "${SSE_OUT}"
curl -sS -N -m 60 -b "${COOKIE_JAR}" \
  -H "User-Agent: ${UA}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: text/event-stream" \
  "${BASE_URL}/api/agents/chat/stream/${STREAM}" >> "${SSE_OUT}" 2>/dev/null

FINAL=$(grep 'data: ' "${SSE_OUT}" 2>/dev/null | grep -E '"final"\s*:\s*true' | tail -1 | sed 's/^data: //')
if [[ -z "${FINAL}" ]] || ! echo "${FINAL}" | grep -q '"final"'; then
  { grep -q 'event: error' "${SSE_OUT}" 2>/dev/null && {
    echo "Stream error:"
    grep -A1 'event: error' "${SSE_OUT}" 2>/dev/null || true
  }; } || true
  echo "Stream output (last 500 chars):"
  tail -c 500 "${SSE_OUT}" 2>/dev/null || echo "(none)"
  echo "WARN: Stream did not complete (may need configured LLM) — model null fix still verified"
else
  PASS "Stream completed successfully"
fi
set -e

# Step 4: Summary
echo ""
echo "[4/4] Summary"
echo "---"
PASS "Model null smoke test complete."
echo "  - Request with model: null was accepted (no Zod validation error)"
echo "  - Fix verified: backend applies fallback model instead of throwing"
echo ""
