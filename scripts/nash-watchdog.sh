#!/usr/bin/env bash
# Watchdog: polls Nash every 5 seconds to detect the non-responsive condition.
#
# The degraded state is:
#   - /health returns 200 (simple endpoint, no async — always passes)
#   - /api/init hangs or times out (exercises run_async + Backboard)
#
# Usage:
#   export BASE_URL=https://nash.backboard.io
#   export JWT_TOKEN=<bearer token>          # or use REFRESH_TOKEN
#   export REFRESH_TOKEN=<cookie value>
#   ./scripts/nash-watchdog.sh
#
# Optional tuning:
#   POLL_INTERVAL=5          poll frequency in seconds
#   HEALTH_TIMEOUT=5         max seconds for /health
#   INIT_TIMEOUT=15          max seconds for /api/init before declaring failure
#   INIT_WARN_SEC=6          warn (yellow) if /api/init takes longer than this

set -euo pipefail
source .env
BASE_URL="${BASE_URL:-http://localhost:3080}"
JWT_TOKEN="${JWT_TOKEN:-}"
REFRESH_TOKEN="${REFRESH_TOKEN:-}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-5}"
INIT_TIMEOUT="${INIT_TIMEOUT:-15}"
INIT_WARN_SEC="${INIT_WARN_SEC:-6}"

RED='\033[0;31m'
YLW='\033[1;33m'
GRN='\033[0;32m'
RST='\033[0m'

FAIL_COUNT=0
CHECK_COUNT=0
CONSEC_FAIL=0         # consecutive failures; resets on any success
ALERT_THRESHOLD=3     # send email after this many consecutive failures
BODY_FILE="/tmp/nash-watchdog-init-$$.json"
HEALTH_FILE="/tmp/nash-watchdog-health-$$.json"

_send_alert() {
  local subject="$1" body="$2"
  uv run python3 "$(dirname "$0")/nash-alert.py" "${subject}" "${body}" 2>&1 \
    | sed 's/^/  [alert] /' || true
}

_ts()      { date '+%Y-%m-%dT%H:%M:%S'; }
_ms_now()  { perl -MTime::HiRes=time -e 'printf "%d", time()*1000'; }


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

cleanup() { rm -f "${BODY_FILE}" "${HEALTH_FILE}"; }
trap cleanup EXIT

# ── Initial auth ──────────────────────────────────────────────────────────────
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

echo "Nash watchdog"
echo "  BASE_URL        : ${BASE_URL}"
echo "  poll every      : ${POLL_INTERVAL}s"
echo "  /health timeout : ${HEALTH_TIMEOUT}s"
echo "  /api/init timeout: ${INIT_TIMEOUT}s  (warn after ${INIT_WARN_SEC}s)"
echo "Press Ctrl+C to stop."
echo ""

# ── Poll loop ─────────────────────────────────────────────────────────────────
while true; do
  CHECK_COUNT=$((CHECK_COUNT + 1))
  TS="$(_ts)"

  # ── 1. /health ────────────────────────────────────────────────────────────
  T0="$(_ms_now)"
  set +e
  HEALTH_STATUS="$(curl -sS --max-time "${HEALTH_TIMEOUT}" \
    -o "${HEALTH_FILE}" \
    -w "%{http_code}" "${BASE_URL}/health" 2>/dev/null)"
  HEALTH_EXIT=$?
  set -e
  HEALTH_MS=$(( $(_ms_now) - T0 ))
  VER="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    "${HEALTH_FILE}" 2>/dev/null | head -n 1)"
  VER="${VER:-?}"

  if [[ "${HEALTH_EXIT}" -ne 0 || "${HEALTH_STATUS}" != "200" ]]; then
    printf "\a"
    printf "${RED}[%s][?] FAIL /health: http=%s curl_exit=%d (%dms) — server may be down${RST}\n" \
      "${TS}" "${HEALTH_STATUS:-??}" "${HEALTH_EXIT}" "${HEALTH_MS}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    CONSEC_FAIL=$((CONSEC_FAIL + 1))
    if [[ "${CONSEC_FAIL}" -eq "${ALERT_THRESHOLD}" ]]; then
      _send_alert \
        "ALERT: Nash is DOWN ${CONSEC_FAIL}x" \
        "Nash watchdog detected ${CONSEC_FAIL} consecutive failures at ${TS}.

Endpoint: ${BASE_URL}/health
Last HTTP status: ${HEALTH_STATUS:-??}  curl exit: ${HEALTH_EXIT}
Total checks: ${CHECK_COUNT}  Total failures: ${FAIL_COUNT}

Check App Runner logs and restart if needed."
    fi
    sleep "${POLL_INTERVAL}"
    continue
  fi

  # ── 2. /api/init (authenticated; exercises run_async + Backboard) ──────────
  T0="$(_ms_now)"
  set +e
  INIT_STATUS="$(curl -sS --max-time "${INIT_TIMEOUT}" \
    -o "${BODY_FILE}" -w "%{http_code}" \
    -H "Authorization: Bearer ${JWT_TOKEN}" \
    "${BASE_URL}/api/init" 2>/dev/null)"
  INIT_EXIT=$?
  set -e
  INIT_MS=$(( $(_ms_now) - T0 ))

  # Auto-refresh JWT on 401 and retry once
  if [[ "${INIT_STATUS}" == "401" && -n "${REFRESH_TOKEN}" ]]; then
    _refresh_jwt
    T0="$(_ms_now)"
    set +e
    INIT_STATUS="$(curl -sS --max-time "${INIT_TIMEOUT}" \
      -o "${BODY_FILE}" -w "%{http_code}" \
      -H "Authorization: Bearer ${JWT_TOKEN}" \
      "${BASE_URL}/api/init" 2>/dev/null)"
    INIT_EXIT=$?
    set -e
    INIT_MS=$(( $(_ms_now) - T0 ))
  fi

  # ── Evaluate /api/init result ──────────────────────────────────────────────
  if [[ "${INIT_EXIT}" -eq 28 ]]; then
    # curl exit 28 = operation timed out — this IS the non-responsive condition
    printf "\a"
    printf "${RED}[%s][%s] HUNG  /api/init: TIMED OUT after %ds — NON-RESPONSIVE CONDITION DETECTED (check=%d fails=%d)${RST}\n" \
      "${TS}" "${VER}" "${INIT_TIMEOUT}" "${CHECK_COUNT}" "$((FAIL_COUNT + 1))"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    CONSEC_FAIL=$((CONSEC_FAIL + 1))
    if [[ "${CONSEC_FAIL}" -eq "${ALERT_THRESHOLD}" ]]; then
      _send_alert \
        "ALERT: Nash is HUNG ${CONSEC_FAIL}x" \
        "Nash watchdog detected ${CONSEC_FAIL} consecutive timeouts on /api/init at ${TS}.

Endpoint: ${BASE_URL}/api/init
Condition: HUNG — timed out after ${INIT_TIMEOUT}s (non-responsive / run_async stall)
Version: ${VER}  Total checks: ${CHECK_COUNT}  Total failures: ${FAIL_COUNT}

Check App Runner logs and restart if needed."
    fi

  elif [[ "${INIT_EXIT}" -ne 0 || "${INIT_STATUS}" != "200" ]]; then
    printf "\a"
    printf "${RED}[%s][%s] FAIL  /api/init: http=%s curl_exit=%d (%dms) (check=%d fails=%d)${RST}\n" \
      "${TS}" "${VER}" "${INIT_STATUS:-??}" "${INIT_EXIT}" "${INIT_MS}" "${CHECK_COUNT}" "$((FAIL_COUNT + 1))"
    if [[ -s "${BODY_FILE}" ]]; then
      printf "        response: "; head -c 160 "${BODY_FILE}"; echo ""
    fi
    FAIL_COUNT=$((FAIL_COUNT + 1))
    CONSEC_FAIL=$((CONSEC_FAIL + 1))
    if [[ "${CONSEC_FAIL}" -eq "${ALERT_THRESHOLD}" ]]; then
      _send_alert \
        "ALERT: Nash is DOWN ${CONSEC_FAIL}x" \
        "Nash watchdog detected ${CONSEC_FAIL} consecutive errors on /api/init at ${TS}.

Endpoint: ${BASE_URL}/api/init
Last HTTP status: ${INIT_STATUS:-??}  curl exit: ${INIT_EXIT}  response time: ${INIT_MS}ms
Version: ${VER}  Total checks: ${CHECK_COUNT}  Total failures: ${FAIL_COUNT}

Check App Runner logs and restart if needed."
    fi

  elif [[ "${INIT_MS}" -gt $((INIT_WARN_SEC * 1000)) ]]; then
    printf "${YLW}[%s][%s] SLOW  /api/init: %dms (>${INIT_WARN_SEC}s warn) health=%dms (check=%d fails=%d)${RST}\n" \
      "${TS}" "${VER}" "${INIT_MS}" "${HEALTH_MS}" "${CHECK_COUNT}" "${FAIL_COUNT}"
    CONSEC_FAIL=0

  else
    printf "${GRN}[%s][%s] OK    health=%dms  init=%dms  (check=%d fails=%d)${RST}\n" \
      "${TS}" "${VER}" "${HEALTH_MS}" "${INIT_MS}" "${CHECK_COUNT}" "${FAIL_COUNT}"
    CONSEC_FAIL=0
  fi

  sleep "${POLL_INTERVAL}"
done
