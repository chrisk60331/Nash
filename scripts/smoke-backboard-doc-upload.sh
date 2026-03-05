#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

BASE_URL="${BASE_URL:-https://app.backboard.io/api}"
API_KEY="${BACKBOARD_API_KEY:-}"
ASSISTANT_ID="${BACKBOARD_ASSISTANT_ID:-}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-2}"
MAX_POLLS="${MAX_POLLS:-90}"
TEST_FILE="${TEST_FILE:-}"

if [[ -z "${API_KEY}" ]]; then
  echo "FAIL: BACKBOARD_API_KEY is required"
  exit 1
fi

if [[ -z "${ASSISTANT_ID}" ]]; then
  echo "FAIL: BACKBOARD_ASSISTANT_ID is required"
  exit 1
fi

TMP_FILE=""
if [[ -n "${TEST_FILE}" ]]; then
  if [[ ! -f "${TEST_FILE}" ]]; then
    echo "FAIL: TEST_FILE does not exist: ${TEST_FILE}"
    exit 1
  fi
  UPLOAD_FILE="${TEST_FILE}"
else
  TMP_FILE="/tmp/bb-smoke-doc-$$.txt"
  cat > "${TMP_FILE}" <<'EOF'
Backboard document upload smoke test.
This file validates assistant document ingestion and indexing.
EOF
  UPLOAD_FILE="${TMP_FILE}"
fi

echo "Running Backboard doc smoke test"
echo "BASE_URL=${BASE_URL}"
echo "ASSISTANT_ID=${ASSISTANT_ID}"
echo "UPLOAD_FILE=${UPLOAD_FILE}"

UPLOAD_BODY="/tmp/bb-upload-body-$$.json"
UPLOAD_STATUS="$(
  curl -sS -o "${UPLOAD_BODY}" -w "%{http_code}" \
    -X POST \
    -H "X-API-Key: ${API_KEY}" \
    -F "file=@${UPLOAD_FILE}" \
    "${BASE_URL}/assistants/${ASSISTANT_ID}/documents"
)"

if [[ "${UPLOAD_STATUS}" != "200" && "${UPLOAD_STATUS}" != "201" ]]; then
  echo "FAIL: upload returned HTTP ${UPLOAD_STATUS}"
  cat "${UPLOAD_BODY}"
  rm -f "${UPLOAD_BODY}" "${TMP_FILE}"
  exit 1
fi

DOCUMENT_ID="$(
  sed -n 's/.*"document_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${UPLOAD_BODY}" | head -n 1
)"

if [[ -z "${DOCUMENT_ID}" ]]; then
  echo "FAIL: could not parse document_id from upload response"
  cat "${UPLOAD_BODY}"
  rm -f "${UPLOAD_BODY}" "${TMP_FILE}"
  exit 1
fi

echo "PASS: upload accepted, document_id=${DOCUMENT_ID}"

STATUS_BODY="/tmp/bb-status-body-$$.json"
FINAL_STATUS=""
for ((i=1; i<=MAX_POLLS; i++)); do
  STATUS_CODE="$(
    curl -sS -o "${STATUS_BODY}" -w "%{http_code}" \
      -H "X-API-Key: ${API_KEY}" \
      "${BASE_URL}/documents/${DOCUMENT_ID}/status"
  )"

  if [[ "${STATUS_CODE}" != "200" ]]; then
    echo "FAIL: status poll returned HTTP ${STATUS_CODE} on attempt ${i}"
    cat "${STATUS_BODY}"
    rm -f "${UPLOAD_BODY}" "${STATUS_BODY}" "${TMP_FILE}"
    exit 1
  fi

  STATUS_VALUE="$(
    sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${STATUS_BODY}" | head -n 1
  )"

  echo "poll ${i}/${MAX_POLLS}: status=${STATUS_VALUE:-unknown}"

  if [[ "${STATUS_VALUE}" == "indexed" ]]; then
    FINAL_STATUS="indexed"
    break
  fi
  if [[ "${STATUS_VALUE}" == "failed" ]]; then
    FINAL_STATUS="failed"
    break
  fi

  sleep "${POLL_INTERVAL_SECONDS}"
done

if [[ "${FINAL_STATUS}" != "indexed" ]]; then
  echo "FAIL: document did not reach indexed state (final=${FINAL_STATUS:-timeout})"
  cat "${STATUS_BODY}"
  rm -f "${UPLOAD_BODY}" "${STATUS_BODY}" "${TMP_FILE}"
  exit 1
fi

echo "PASS: document indexed successfully"
echo "Smoke test passed."

rm -f "${UPLOAD_BODY}" "${STATUS_BODY}" "${TMP_FILE}"
