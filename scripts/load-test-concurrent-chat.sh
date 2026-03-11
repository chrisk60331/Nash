#!/usr/bin/env bash
# Load test: simulates concurrent users chatting to stress-test the Docker container
# under App Runner-like constraints (mem_limit, cpuset in docker-compose.yml).
# Each virtual user runs sequential chat rounds (start → stream) in a background job.
# Uses curl only.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL="${BASE_URL:-http://localhost:3080}"
JWT_TOKEN="${JWT_TOKEN:-}"
REFRESH_TOKEN="${REFRESH_TOKEN:-}"

CHAT_ENDPOINT_NAME="${CHAT_ENDPOINT_NAME:-cerebras}"
CHAT_ENDPOINT="${CHAT_ENDPOINT:-cerebras}"
CHAT_MODEL="${CHAT_MODEL:-cerebras/meta-llama/llama-3.1-8b-instruct}"

# Number of concurrent virtual users
USERS="${USERS:-5}"
# Sequential chat rounds each user completes (turn 1 starts new convo, turns 2+ continue it)
ROUNDS="${ROUNDS:-3}"
# Short prompt to keep LLM responses fast; overridable for longer responses
PROMPT_TEXT="${PROMPT_TEXT:-Reply with exactly one sentence.}"
# Max seconds to wait for a single stream to complete
STREAM_MAX_TIME="${STREAM_MAX_TIME:-90}"
# Keep per-user debug files after the run (0 = delete on exit)
KEEP_DEBUG="${KEEP_DEBUG:-0}"

# ── Resolve auth token ────────────────────────────────────────────────────────
if [[ -z "${JWT_TOKEN}" && -n "${REFRESH_TOKEN}" ]]; then
  REFRESH_BODY="/tmp/nash-lt-refresh-$$.json"
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
  echo "FAIL: JWT_TOKEN (or REFRESH_TOKEN) is required."
  exit 1
fi

AUTH_HEADER="Authorization: Bearer ${JWT_TOKEN}"

# ── Shared tmp dir for this run ───────────────────────────────────────────────
RUN_ID="$$-$(date +%s)"
TMP_DIR="/tmp/nash-lt-${RUN_ID}"
mkdir -p "${TMP_DIR}"

cleanup() {
  if [[ "${KEEP_DEBUG}" != "1" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

# ── Header ────────────────────────────────────────────────────────────────────
echo "============================================================"
echo "  Nash concurrent chat load test"
echo "  BASE_URL     : ${BASE_URL}"
echo "  ENDPOINT     : ${CHAT_ENDPOINT_NAME}  model=${CHAT_MODEL}"
echo "  USERS        : ${USERS}  ROUNDS: ${ROUNDS}"
echo "  STREAM_TIMEOUT: ${STREAM_MAX_TIME}s"
echo "  KEEP_DEBUG   : ${KEEP_DEBUG}"
echo "============================================================"
echo ""

# ── Per-user worker function ──────────────────────────────────────────────────
# Writes one line per round to ${TMP_DIR}/user-${uid}.tsv:
#   round  start_status  stream_status  ttfb_ms  total_ms  final_events  text_events
run_user() {
  local uid="$1"
  local out_tsv="${TMP_DIR}/user-${uid}.tsv"
  local conversation_id=""
  local parent_message_id="00000000-0000-0000-0000-000000000000"

  echo "idx	start_http	stream_http	ttfb_ms	total_ms	final_events	text_events" > "${out_tsv}"

  local round
  for round in $(seq 1 "${ROUNDS}"); do
    local start_body="${TMP_DIR}/u${uid}-r${round}-start.json"
    local sse_body="${TMP_DIR}/u${uid}-r${round}-sse.txt"
    local sse_headers="${TMP_DIR}/u${uid}-r${round}-hdrs.txt"

    local t0
    t0="$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')"

    # ── Start chat turn ──────────────────────────────────────────────────────
    local conv_field
    if [[ -z "${conversation_id}" ]]; then
      conv_field='""'
    else
      conv_field="\"${conversation_id}\""
    fi

    local start_status
    start_status="$(
      curl -sS -o "${start_body}" -w "%{http_code}" \
        --max-time 30 \
        -X POST \
        -H "${AUTH_HEADER}" \
        -H "Content-Type: application/json" \
        -d "{
          \"conversationId\": ${conv_field},
          \"text\": \"${PROMPT_TEXT}\",
          \"endpoint\": \"${CHAT_ENDPOINT}\",
          \"endpointType\": \"custom\",
          \"model\": \"${CHAT_MODEL}\",
          \"parentMessageId\": \"${parent_message_id}\"
        }" \
        "${BASE_URL}/api/agents/chat/${CHAT_ENDPOINT_NAME}"
    )" || true

    local stream_id
    stream_id="$(
      sed -n 's/.*"streamId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${start_body}" 2>/dev/null | head -n 1
    )"

    # Capture conversationId from start response for subsequent rounds
    local new_conv
    new_conv="$(
      sed -n 's/.*"conversationId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${start_body}" 2>/dev/null | head -n 1
    )"
    if [[ -n "${new_conv}" ]]; then
      conversation_id="${new_conv}"
    fi

    local t_start
    t_start="$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')"
    local ttfb_ms=$(( t_start - t0 ))

    if [[ "${start_status}" != "200" || -z "${stream_id}" ]]; then
      echo "${round}	${start_status}	-	${ttfb_ms}	-	0	0" >> "${out_tsv}"
      continue
    fi

    # ── Consume SSE stream ───────────────────────────────────────────────────
    local stream_status
    set +e
    stream_status="$(
      curl -sS -N \
        --max-time "${STREAM_MAX_TIME}" \
        -D "${sse_headers}" \
        -o "${sse_body}" \
        -w "%{http_code}" \
        -H "${AUTH_HEADER}" \
        -H "Accept: text/event-stream" \
        "${BASE_URL}/api/agents/chat/stream/${stream_id}"
    )" || stream_status="000"
    set -e

    local t1
    t1="$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')"
    local total_ms=$(( t1 - t0 ))

    local final_events text_events
    final_events="$(grep -Ec '"final"[[:space:]]*:[[:space:]]*true' "${sse_body}" 2>/dev/null || echo 0)"
    text_events="$(grep -Ec '"type"[[:space:]]*:[[:space:]]*"text"' "${sse_body}" 2>/dev/null || echo 0)"

    # Extract responseMessageId from final event to chain next round's parentMessageId
    local resp_msg_id
    resp_msg_id="$(
      grep '"final"[[:space:]]*:[[:space:]]*true' "${sse_body}" 2>/dev/null \
        | sed -n 's/.*"responseMessageId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
        | head -n 1
    )" || true
    if [[ -n "${resp_msg_id}" ]]; then
      parent_message_id="${resp_msg_id}"
    fi

    echo "${round}	${start_status}	${stream_status}	${ttfb_ms}	${total_ms}	${final_events}	${text_events}" >> "${out_tsv}"

    if [[ "${KEEP_DEBUG}" != "1" ]]; then
      rm -f "${start_body}" "${sse_body}" "${sse_headers}"
    fi
  done
}

# ── Launch all users in parallel ──────────────────────────────────────────────
echo "Spawning ${USERS} virtual user(s)..."
WALL_T0="$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')"

declare -a PIDS=()
for uid in $(seq 1 "${USERS}"); do
  run_user "${uid}" &
  PIDS+=($!)
done

# ── Wait for all workers ──────────────────────────────────────────────────────
WORKER_FAILURES=0
for pid in "${PIDS[@]}"; do
  if ! wait "${pid}"; then
    WORKER_FAILURES=$(( WORKER_FAILURES + 1 ))
  fi
done

WALL_T1="$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')"
WALL_MS=$(( WALL_T1 - WALL_T0 ))
WALL_SEC_FRAC="$(echo "${WALL_MS}" | awk '{printf "%.2f", $1/1000}')"

echo ""
echo "All ${USERS} worker(s) finished in ${WALL_SEC_FRAC}s"
echo ""

# ── Aggregate results ─────────────────────────────────────────────────────────
TOTAL_ROUNDS=0
TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_STREAM_FAIL=0
SUM_TTFB=0
SUM_TOTAL=0
COUNT_TTFB=0

echo "============================================================"
echo "  Per-user summary"
echo "------------------------------------------------------------"
printf "  %-6s %-8s %-8s %-8s %-10s %-10s %-8s\n" \
  "user" "pass" "fail" "str_fail" "avg_ttfb" "avg_total" "rounds"

for uid in $(seq 1 "${USERS}"); do
  tsv="${TMP_DIR}/user-${uid}.tsv"
  if [[ ! -f "${tsv}" ]]; then
    printf "  %-6s  (no output - worker may have crashed)\n" "u${uid}"
    TOTAL_FAIL=$(( TOTAL_FAIL + ROUNDS ))
    TOTAL_ROUNDS=$(( TOTAL_ROUNDS + ROUNDS ))
    continue
  fi

  user_pass=0
  user_fail=0
  user_sfail=0
  user_ttfb_sum=0
  user_total_sum=0
  user_count=0

  while IFS=$'\t' read -r round start_http stream_http ttfb_ms total_ms final_events text_events; do
    [[ "${round}" == "idx" ]] && continue
    TOTAL_ROUNDS=$(( TOTAL_ROUNDS + 1 ))

    local_pass=1
    if [[ "${start_http}" != "200" ]]; then
      user_fail=$(( user_fail + 1 ))
      TOTAL_FAIL=$(( TOTAL_FAIL + 1 ))
      local_pass=0
    fi
    if [[ "${stream_http}" != "200" ]]; then
      user_sfail=$(( user_sfail + 1 ))
      TOTAL_STREAM_FAIL=$(( TOTAL_STREAM_FAIL + 1 ))
      if [[ "${local_pass}" == "1" ]]; then
        local_pass=0
        user_fail=$(( user_fail + 1 ))
        TOTAL_FAIL=$(( TOTAL_FAIL + 1 ))
      fi
    fi
    if [[ "${local_pass}" == "1" && "${final_events}" -ge 1 ]]; then
      user_pass=$(( user_pass + 1 ))
      TOTAL_PASS=$(( TOTAL_PASS + 1 ))
    elif [[ "${local_pass}" == "1" ]]; then
      user_fail=$(( user_fail + 1 ))
      TOTAL_FAIL=$(( TOTAL_FAIL + 1 ))
    fi

    if [[ "${ttfb_ms}" =~ ^[0-9]+$ ]]; then
      user_ttfb_sum=$(( user_ttfb_sum + ttfb_ms ))
      user_count=$(( user_count + 1 ))
      SUM_TTFB=$(( SUM_TTFB + ttfb_ms ))
      COUNT_TTFB=$(( COUNT_TTFB + 1 ))
    fi
    if [[ "${total_ms}" =~ ^[0-9]+$ ]]; then
      user_total_sum=$(( user_total_sum + total_ms ))
      SUM_TOTAL=$(( SUM_TOTAL + total_ms ))
    fi
  done < "${tsv}"

  avg_ttfb="-"
  avg_total="-"
  if [[ "${user_count}" -gt 0 ]]; then
    avg_ttfb="$(echo "${user_ttfb_sum} ${user_count}" | awk '{printf "%dms", $1/$2}')"
    avg_total="$(echo "${user_total_sum} ${user_count}" | awk '{printf "%dms", $1/$2}')"
  fi

  printf "  %-6s %-8s %-8s %-8s %-10s %-10s %-8s\n" \
    "u${uid}" "${user_pass}" "${user_fail}" "${user_sfail}" "${avg_ttfb}" "${avg_total}" "${ROUNDS}"
done

echo "------------------------------------------------------------"
AVG_TTFB_ALL="-"
AVG_TOTAL_ALL="-"
if [[ "${COUNT_TTFB}" -gt 0 ]]; then
  AVG_TTFB_ALL="$(echo "${SUM_TTFB} ${COUNT_TTFB}" | awk '{printf "%dms", $1/$2}')"
  AVG_TOTAL_ALL="$(echo "${SUM_TOTAL} ${COUNT_TTFB}" | awk '{printf "%dms", $1/$2}')"
fi

RPS="$(echo "${TOTAL_PASS} ${WALL_MS}" | awk '{if ($2>0) printf "%.2f", $1/($2/1000); else print "n/a"}')"

echo ""
echo "============================================================"
echo "  Overall results"
echo "------------------------------------------------------------"
echo "  Total rounds       : ${TOTAL_ROUNDS}"
echo "  Passed             : ${TOTAL_PASS}"
echo "  Failed             : ${TOTAL_FAIL}  (stream_fail: ${TOTAL_STREAM_FAIL})"
echo "  Avg TTFB (start)   : ${AVG_TTFB_ALL}"
echo "  Avg total (stream) : ${AVG_TOTAL_ALL}"
echo "  Wall time          : ${WALL_SEC_FRAC}s"
echo "  Throughput         : ${RPS} successful rounds/sec"
echo "  Worker crashes     : ${WORKER_FAILURES}"
echo "============================================================"

if [[ "${KEEP_DEBUG}" == "1" ]]; then
  echo ""
  echo "Debug files retained in: ${TMP_DIR}"
fi

if [[ "${TOTAL_FAIL}" -gt 0 || "${WORKER_FAILURES}" -gt 0 ]]; then
  echo ""
  echo "LOAD TEST FAILED  (${TOTAL_FAIL} round failure(s), ${WORKER_FAILURES} worker crash(es))"
  exit 1
fi

echo ""
echo "LOAD TEST PASSED"
