#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
JWT_TOKEN="${JWT_TOKEN:-}"
REFRESH_TOKEN="${REFRESH_TOKEN:-}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-5}"
INIT_TIMEOUT="${INIT_TIMEOUT:-15}"
INIT_CONCURRENCY="${INIT_CONCURRENCY:-4}"
INIT_REQUESTS="${INIT_REQUESTS:-8}"

HEALTH_FILE="/tmp/nash-smoke-health-$$.json"
WORK_DIR="/tmp/nash-smoke-init-$$"

cleanup() { rm -f "${HEALTH_FILE}"; rm -rf "${WORK_DIR}"; }
trap cleanup EXIT

_refresh_jwt() {
  local raw
  raw="$(curl -sS --max-time 8 \
    -H "Cookie: refreshToken=${REFRESH_TOKEN}" \
    "${BASE_URL}/api/auth/refresh" 2>/dev/null || true)"
  local tok
  tok="$(echo "${raw}" | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  if [[ -n "${tok}" ]]; then
    JWT_TOKEN="${tok}"
  fi
}

if [[ -z "${JWT_TOKEN}" && -n "${REFRESH_TOKEN}" ]]; then
  echo "Refreshing JWT from REFRESH_TOKEN..."
  _refresh_jwt
fi

if [[ -z "${JWT_TOKEN}" ]]; then
  echo "ERROR: set JWT_TOKEN or REFRESH_TOKEN before running."
  echo "  export JWT_TOKEN=<bearer-token>"
  echo "  export REFRESH_TOKEN=<cookie-value>"
  exit 1
fi

echo "Nash smoke test"
echo "  BASE_URL        : ${BASE_URL}"
echo "  /health timeout : ${HEALTH_TIMEOUT}s"
echo "  /api/init timeout: ${INIT_TIMEOUT}s"
echo "  /api/init requests: ${INIT_REQUESTS}"
echo "  /api/init concurrency: ${INIT_CONCURRENCY}"
echo ""

health_status="$(curl -sS --max-time "${HEALTH_TIMEOUT}" \
  -o "${HEALTH_FILE}" -w "%{http_code}" \
  "${BASE_URL}/health" 2>/dev/null)"

if [[ "${health_status}" != "200" ]]; then
  echo "FAIL: GET /health returned ${health_status}"
  echo "Response:"
  rg -n "" "${HEALTH_FILE}" || true
  exit 1
fi

mkdir -p "${WORK_DIR}"
fail_count=0
completed=0

_run_init() {
  local idx="$1"
  local body="${WORK_DIR}/init-${idx}.json"
  local status
  status="$(curl -sS --max-time "${INIT_TIMEOUT}" \
    -o "${body}" -w "%{http_code}" \
    -H "Authorization: Bearer ${JWT_TOKEN}" \
    "${BASE_URL}/api/init" 2>/dev/null)"
  if [[ "${status}" != "200" ]]; then
    echo "FAIL: /api/init #${idx} returned ${status}"
    rg -n "" "${body}" || true
    return 1
  fi
  if ! rg -q '"agents"' "${body}"; then
    echo "FAIL: /api/init #${idx} missing agents payload"
    rg -n "" "${body}" || true
    return 1
  fi
  return 0
}

while [[ "${completed}" -lt "${INIT_REQUESTS}" ]]; do
  batch=0
  pids=()
  while [[ "${batch}" -lt "${INIT_CONCURRENCY}" && "${completed}" -lt "${INIT_REQUESTS}" ]]; do
    completed=$((completed + 1))
    _run_init "${completed}" &
    pids+=("$!")
    batch=$((batch + 1))
  done
  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      fail_count=$((fail_count + 1))
    fi
  done
done

if [[ "${fail_count}" -ne 0 ]]; then
  echo "FAIL: /api/init had ${fail_count} failures"
  exit 1
fi

echo "PASS: /health and /api/init (${INIT_REQUESTS} requests, concurrency ${INIT_CONCURRENCY})"
echo "Smoke test passed."
