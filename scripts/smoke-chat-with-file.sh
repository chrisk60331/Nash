#!/usr/bin/env bash
# Smoke test: Nash chat stream with attached file (repros Backboard HTTP 400 after file processing).
# Uses curl only. Auth: set JWT_TOKEN in .env, or set REFRESH_TOKEN (value of refreshToken cookie from DevTools).
# Note: sso_token is written to Session Storage (not Local Storage) after Google login and is removed after first load.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

BASE_URL="${BASE_URL:-http://localhost:3080}"
JWT_TOKEN="${JWT_TOKEN:-}"
REFRESH_TOKEN="${REFRESH_TOKEN:-}"
TEST_FILE="${TEST_FILE:-}"

# If no JWT but we have refresh cookie, get a new access token
if [[ -z "${JWT_TOKEN}" && -n "${REFRESH_TOKEN}" ]]; then
  REFRESH_BODY="/tmp/nash-smoke-refresh-$$.json"
  REFRESH_STATUS="$(
    curl -sS -o "${REFRESH_BODY}" -w "%{http_code}" \
      -X GET \
      -H "Cookie: refreshToken=${REFRESH_TOKEN}" \
      "${BASE_URL}/api/auth/refresh"
  )"
  if [[ "${REFRESH_STATUS}" == "200" ]]; then
    JWT_TOKEN="$(
      sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${REFRESH_BODY}" | head -n 1
    )"
  fi
  rm -f "${REFRESH_BODY}"
fi

if [[ -z "${JWT_TOKEN}" ]]; then
  echo "FAIL: JWT_TOKEN or REFRESH_TOKEN required."
  echo "  - Do NOT use the refresh token as JWT_TOKEN (that returns 401 Invalid token)."
  echo "  - Set REFRESH_TOKEN in .env to the refreshToken cookie value; the script will fetch an access token."
  echo "  - Or set JWT_TOKEN to an access token (e.g. from Network tab Authorization header, or Session Storage sso_token before it is consumed)."
  exit 1
fi

# Small test file (or use TEST_FILE for a PDF to repro Backboard 400)
TMP_FILE=""
if [[ -n "${TEST_FILE}" ]]; then
  if [[ ! -f "${TEST_FILE}" ]]; then
    echo "FAIL: TEST_FILE does not exist: ${TEST_FILE}"
    exit 1
  fi
  UPLOAD_FILE="${TEST_FILE}"
else
  TMP_FILE="/tmp/nash-smoke-chat-$$.txt"
  cat > "${TMP_FILE}" <<'EOF'
Nash chat-with-file smoke test.
EOF
  UPLOAD_FILE="${TMP_FILE}"
fi

echo "Running Nash chat-with-file smoke test"
echo "BASE_URL=${BASE_URL}"
echo "UPLOAD_FILE=${UPLOAD_FILE}"

AUTH_HEADER="Authorization: Bearer ${JWT_TOKEN}"
FILE_ID="smoke-file-$(date +%s)"

# 1) Upload file to Nash
UPLOAD_BODY="/tmp/nash-smoke-upload-$$.json"
UPLOAD_STATUS="$(
  curl -sS -o "${UPLOAD_BODY}" -w "%{http_code}" \
    -X POST \
    -H "${AUTH_HEADER}" \
    -F "file=@${UPLOAD_FILE}" \
    -F "file_id=${FILE_ID}" \
    -F "endpoint=AWS Bedrock" \
    -F "endpointType=custom" \
    "${BASE_URL}/api/files"
)"

if [[ "${UPLOAD_STATUS}" != "200" ]]; then
  echo "FAIL: POST /api/files returned HTTP ${UPLOAD_STATUS}"
  if [[ "${UPLOAD_STATUS}" == "403" ]]; then
    echo "  (403 = Forbidden. Check BASE_URL is the Nash API, e.g. http://localhost:3080, and JWT_TOKEN is valid.)"
  fi
  cat "${UPLOAD_BODY}"
  rm -f "${UPLOAD_BODY}" "${TMP_FILE}"
  exit 1
fi

FILEPATH="$(
  sed -n 's/.*"filepath"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${UPLOAD_BODY}" | head -n 1
)"
if [[ -z "${FILEPATH}" ]]; then
  echo "FAIL: could not parse filepath from upload response"
  cat "${UPLOAD_BODY}"
  rm -f "${UPLOAD_BODY}" "${TMP_FILE}"
  exit 1
fi

echo "PASS: file uploaded, filepath=${FILEPATH}"

# 2) Start chat with file attached
CHAT_START_BODY="/tmp/nash-smoke-start-$$.json"
CHAT_START_STATUS="$(
  curl -sS -o "${CHAT_START_BODY}" -w "%{http_code}" \
    -X POST \
    -H "${AUTH_HEADER}" \
    -H "Content-Type: application/json" \
    -d "{
      \"conversationId\": \"new\",
      \"text\": \"Summarize this file in one sentence.\",
      \"endpoint\": \"AWS Bedrock\",
      \"endpointType\": \"custom\",
      \"model\": \"aws-bedrock/anthropic.claude-3-5-haiku-20241022-v1:0\",
      \"parentMessageId\": \"00000000-0000-0000-0000-000000000000\",
      \"files\": [{\"filepath\": \"${FILEPATH}\"}]
    }" \
    "${BASE_URL}/api/agents/chat/AWS%20Bedrock"
)"

if [[ "${CHAT_START_STATUS}" != "200" ]]; then
  echo "FAIL: POST /api/agents/chat returned HTTP ${CHAT_START_STATUS}"
  cat "${CHAT_START_BODY}"
  rm -f "${UPLOAD_BODY}" "${CHAT_START_BODY}" "${TMP_FILE}"
  exit 1
fi

STREAM_ID="$(
  sed -n 's/.*"streamId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${CHAT_START_BODY}" | head -n 1
)"
if [[ -z "${STREAM_ID}" ]]; then
  echo "FAIL: could not parse streamId from start response"
  cat "${CHAT_START_BODY}"
  rm -f "${UPLOAD_BODY}" "${CHAT_START_BODY}" "${TMP_FILE}"
  exit 1
fi

echo "PASS: chat started, streamId=${STREAM_ID}"

# 3) Consume SSE stream until final or timeout (repro: may see Backboard 400 in stream)
SSE_OUT="/tmp/nash-smoke-sse-$$.txt"
SSE_STATUS="/tmp/nash-smoke-sse-status-$$.txt"
STREAM_URL="${BASE_URL}/api/agents/chat/stream/${STREAM_ID}"
# Timeout ~2 min to allow file processing + stream
STREAM_HTTP="000"
curl -sS -o "${SSE_OUT}" -w "%{http_code}" --max-time 120 \
  -H "${AUTH_HEADER}" \
  -H "Accept: text/event-stream" \
  "${STREAM_URL}" > "${SSE_STATUS}" || true
STREAM_HTTP="$(cat "${SSE_STATUS}" 2>/dev/null || echo "000")"

if [[ "${STREAM_HTTP}" != "200" ]]; then
  echo "FAIL: GET /api/agents/chat/stream returned HTTP ${STREAM_HTTP}"
  head -100 "${SSE_OUT}"
  rm -f "${UPLOAD_BODY}" "${CHAT_START_BODY}" "${SSE_OUT}" "${SSE_STATUS}" "${TMP_FILE}"
  exit 1
fi

# Check for final event (success) or known Backboard error in stream (repro)
if grep -q '"final"[[:space:]]*:[[:space:]]*true' "${SSE_OUT}"; then
  echo "PASS: stream completed with final event"
elif grep -q 'HTTP 400\|BackboardValidationError\|\[Error:' "${SSE_OUT}"; then
  echo "REPRO: stream contained Backboard/API error (expected repro)"
  grep -o '\[Error:[^]]*\]\|HTTP 400[^"]*\|BackboardValidationError[^"]*' "${SSE_OUT}" | head -5 || true
else
  echo "FAIL: stream ended without final event and no recognized error"
  echo "First 50 lines of SSE output:"
  head -50 "${SSE_OUT}"
  rm -f "${UPLOAD_BODY}" "${CHAT_START_BODY}" "${SSE_OUT}" "${SSE_STATUS}" "${TMP_FILE}"
  exit 1
fi

echo "Smoke test passed."
rm -f "${UPLOAD_BODY}" "${CHAT_START_BODY}" "${SSE_OUT}" "${SSE_STATUS}" "${TMP_FILE}"
