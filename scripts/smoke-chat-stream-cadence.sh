#!/usr/bin/env bash
# Smoke test: validates local SSE chat stream cadence using curl only.
# Adds timestamped event metrics to help identify whether burstiness is upstream.
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

CHAT_ENDPOINT_NAME="${CHAT_ENDPOINT_NAME:-Anthropic}"
CHAT_ENDPOINT="${CHAT_ENDPOINT:-Anthropic}"
CHAT_MODEL="${CHAT_MODEL:-anthropic/claude-haiku-4-5-20251001}"
PROMPT_TEXT="${PROMPT_TEXT:-Give me a short 2-sentence summary of current events in India.}"

STREAM_MAX_TIME="${STREAM_MAX_TIME:-120}"
MIN_TEXT_EVENTS="${MIN_TEXT_EVENTS:-8}"
MAX_JUMP_CHARS="${MAX_JUMP_CHARS:-250}"
KEEP_DEBUG="${KEEP_DEBUG:-1}"

# Optional direct-Backboard comparison (curl only).
COMPARE_BACKBOARD="${COMPARE_BACKBOARD:-0}"
BACKBOARD_BASE_URL="${BACKBOARD_BASE_URL:-https://app.backboard.io/api}"
BACKBOARD_API_KEY="${BACKBOARD_API_KEY:-}"
BACKBOARD_ASSISTANT_ID="${BACKBOARD_ASSISTANT_ID:-}"

TMP_ID="$$-$(date +%s)"
START_BODY="/tmp/nash-cadence-start-${TMP_ID}.json"
SSE_OUT="/tmp/nash-cadence-sse-${TMP_ID}.txt"
SSE_TIMED="/tmp/nash-cadence-sse-timed-${TMP_ID}.txt"
SSE_EVENTS="/tmp/nash-cadence-events-${TMP_ID}.tsv"
SSE_TRACE="/tmp/nash-cadence-trace-${TMP_ID}.log"
SSE_HEADERS="/tmp/nash-cadence-headers-${TMP_ID}.txt"
REFRESH_BODY="/tmp/nash-cadence-refresh-${TMP_ID}.json"

BB_THREAD_BODY="/tmp/nash-cadence-bb-thread-${TMP_ID}.json"
BB_TIMED="/tmp/nash-cadence-bb-timed-${TMP_ID}.txt"
BB_EVENTS="/tmp/nash-cadence-bb-events-${TMP_ID}.tsv"
BB_TRACE="/tmp/nash-cadence-bb-trace-${TMP_ID}.log"
BB_HEADERS="/tmp/nash-cadence-bb-headers-${TMP_ID}.txt"

print_event_snapshot() {
  local label="$1"
  local file="$2"
  echo "${label} (first 10 rows):"
  head -n 11 "${file}" || true
  echo ""
}

cleanup() {
  if [[ "${KEEP_DEBUG}" != "1" ]]; then
    rm -f \
      "${START_BODY}" "${SSE_OUT}" "${SSE_TIMED}" "${SSE_EVENTS}" "${SSE_TRACE}" "${SSE_HEADERS}" "${REFRESH_BODY}" \
      /tmp/nash-cadence-resume-*-"${TMP_ID}".txt /tmp/nash-cadence-resume-*-headers-"${TMP_ID}".txt \
      "${BB_THREAD_BODY}" "${BB_TIMED}" "${BB_EVENTS}" "${BB_TRACE}" "${BB_HEADERS}"
  fi
}
trap cleanup EXIT

if [[ -z "${JWT_TOKEN}" && -n "${REFRESH_TOKEN}" ]]; then
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
fi

if [[ -z "${JWT_TOKEN}" ]]; then
  echo "FAIL: JWT_TOKEN (or REFRESH_TOKEN) is required."
  exit 1
fi

AUTH_HEADER="Authorization: Bearer ${JWT_TOKEN}"

echo "Running stream cadence smoke test"
echo "BASE_URL=${BASE_URL}"
echo "ENDPOINT=${CHAT_ENDPOINT_NAME} model=${CHAT_MODEL}"
echo "KEEP_DEBUG=${KEEP_DEBUG}"
echo "COMPARE_BACKBOARD=${COMPARE_BACKBOARD}"
echo ""

START_STATUS="$(
  curl -sS -o "${START_BODY}" -w "%{http_code}" \
    -X POST \
    -H "${AUTH_HEADER}" \
    -H "Content-Type: application/json" \
    -d "{
      \"conversationId\": \"\",
      \"text\": \"${PROMPT_TEXT}\",
      \"endpoint\": \"${CHAT_ENDPOINT}\",
      \"endpointType\": \"custom\",
      \"model\": \"${CHAT_MODEL}\",
      \"parentMessageId\": \"00000000-0000-0000-0000-000000000000\"
    }" \
    "${BASE_URL}/api/agents/chat/${CHAT_ENDPOINT_NAME}"
)"

if [[ "${START_STATUS}" != "200" ]]; then
  echo "FAIL: start chat returned HTTP ${START_STATUS}"
  cat "${START_BODY}"
  exit 1
fi

STREAM_ID="$(
  sed -n 's/.*"streamId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${START_BODY}" | head -n 1
)"
if [[ -z "${STREAM_ID}" ]]; then
  echo "FAIL: could not parse streamId"
  cat "${START_BODY}"
  exit 1
fi

echo "PASS: started stream ${STREAM_ID}"

STREAM_URL="${BASE_URL}/api/agents/chat/stream/${STREAM_ID}"
set +e
curl -sS -N \
  --max-time "${STREAM_MAX_TIME}" \
  --trace-time \
  --trace-ascii "${SSE_TRACE}" \
  -D "${SSE_HEADERS}" \
  -H "${AUTH_HEADER}" \
  -H "Accept: text/event-stream" \
  "${STREAM_URL}" \
  | perl -MTime::HiRes=time -ne 'printf("%.3f\t%s", time(), $_);' > "${SSE_TIMED}"
CURL_EXIT=${PIPESTATUS[0]}
set -e

cut -f2- "${SSE_TIMED}" > "${SSE_OUT}"
STREAM_HTTP="$(
  awk '/^HTTP\// {code=$2} END {if (code == "") print "000"; else print code}' "${SSE_HEADERS}"
)"
if [[ "${STREAM_HTTP}" != "200" ]]; then
  echo "FAIL: stream GET returned HTTP ${STREAM_HTTP} (curl_exit=${CURL_EXIT})"
  head -n 60 "${SSE_OUT}" || true
  exit 1
fi

FINAL_COUNT="$(grep -Ec '"final"[[:space:]]*:[[:space:]]*true' "${SSE_OUT}" || true)"
TEXT_EVENT_COUNT="$(
  grep -E '"type"[[:space:]]*:[[:space:]]*"text"' "${SSE_OUT}" | wc -l | tr -d ' '
)"

METRICS="$(
  awk -v events_file="${SSE_EVENTS}" '
    BEGIN {
      OFS="\t";
      print "idx", "ts", "line_len", "jump", "gap_sec" > events_file;
    }
    /"type"[[:space:]]*:[[:space:]]*"text"/ {
      split($0, parts, "\t");
      ts = parts[1];
      line = parts[2];
      n++;
      len=length(line);
      if (n==1) first=len;
      if (n==2) second=len;
      if (n>1) {
        jump=len-prev_len;
        if (jump>max_jump) max_jump=jump;
        gap=ts-prev_ts;
        if (gap>max_gap) max_gap=gap;
      }
      if (n==1) {
        jump=0;
        gap=0;
      }
      print n, ts, len, jump, gap >> events_file;
      prev_len=len;
      prev_ts=ts;
    }
    END {
      if (n==0) {
        print "0 0 0 0 0";
      } else if (n==1) {
        print n, first, first, 0, 0;
      } else {
        print n, first, second, max_jump+0, max_gap+0;
      }
    }
  ' "${SSE_TIMED}"
)"

EVENTS_FROM_AWK="$(echo "${METRICS}" | awk "{print \$1}")"
FIRST_LEN="$(echo "${METRICS}" | awk "{print \$2}")"
SECOND_LEN="$(echo "${METRICS}" | awk "{print \$3}")"
MAX_JUMP="$(echo "${METRICS}" | awk "{print \$4}")"
MAX_GAP_SEC="$(echo "${METRICS}" | awk "{print \$5}")"
RECV_BLOCKS="$(grep -c 'Recv data' "${SSE_TRACE}" || true)"

echo ""
echo "=== Stream cadence metrics ==="
echo "text_events=${TEXT_EVENT_COUNT} (awk_count=${EVENTS_FROM_AWK})"
echo "first_text_line_len=${FIRST_LEN}"
echo "second_text_line_len=${SECOND_LEN}"
echo "max_jump_between_text_lines=${MAX_JUMP}"
echo "max_gap_seconds_between_text_lines=${MAX_GAP_SEC}"
echo "curl_recv_blocks=${RECV_BLOCKS}"
echo "final_events=${FINAL_COUNT}"
echo "curl_exit=${CURL_EXIT}"
echo ""

FAILURES=0
if [[ "${FINAL_COUNT}" -lt 1 ]]; then
  echo "FAIL: missing final event"
  FAILURES=$((FAILURES + 1))
fi

if [[ "${TEXT_EVENT_COUNT}" -lt "${MIN_TEXT_EVENTS}" ]]; then
  echo "FAIL: too few text events (${TEXT_EVENT_COUNT} < ${MIN_TEXT_EVENTS})"
  FAILURES=$((FAILURES + 1))
fi

if [[ "${MAX_JUMP}" -gt "${MAX_JUMP_CHARS}" ]]; then
  echo "FAIL: bursty stream (max jump ${MAX_JUMP} > ${MAX_JUMP_CHARS})"
  FAILURES=$((FAILURES + 1))
fi

print_event_snapshot "Timestamped local text-event timeline" "${SSE_EVENTS}"

# --- Phase 2: Resume reconnect ---
# The frontend fires a resume request almost immediately after receiving
# the final event (before the server finishes post-stream cleanup like
# saving conversation meta).  We test TWO timings:
#   a) immediate (0ms delay) — catches the race where generate() hasn't
#      finished cleanup yet and the stream is still in _streams
#   b) after 2s — catches the steady-state case
# Both must return a clean {final:true, completed:true} with no re-run.

_check_resume() {
  local label="$1"
  local delay="$2"
  local out="/tmp/nash-cadence-resume-${label}-${TMP_ID}.txt"
  local hdrs="/tmp/nash-cadence-resume-${label}-headers-${TMP_ID}.txt"

  if [[ "${delay}" != "0" ]]; then
    sleep "${delay}"
  fi

  local status
  set +e
  status="$(
    curl -sS -o "${out}" -w "%{http_code}" \
      --max-time 30 \
      -D "${hdrs}" \
      -H "${AUTH_HEADER}" \
      -H "Accept: text/event-stream" \
      "${STREAM_URL}?resume=true"
  )"
  set -e

  local final_n created_n text_n error_n lines_n
  final_n="$(grep -Ec '"final"[[:space:]]*:[[:space:]]*true' "${out}" || true)"
  created_n="$(grep -Ec '"created"[[:space:]]*:[[:space:]]*true' "${out}" || true)"
  text_n="$(grep -Ec '"type"[[:space:]]*:[[:space:]]*"text"' "${out}" || true)"
  error_n="$(grep -Ec '"error"[[:space:]]*:' "${out}" || true)"
  lines_n="$(grep -c 'data:' "${out}" || true)"

  echo "  ${label}: http=${status} data_lines=${lines_n} final=${final_n} created=${created_n} text=${text_n} errors=${error_n}"

  local failed=0
  if [[ "${status}" != "200" ]]; then
    echo "  FAIL (${label}): resume returned HTTP ${status} (expected 200)"
    failed=1
  elif [[ "${final_n}" -lt 1 ]]; then
    echo "  FAIL (${label}): resume missing final event"
    failed=1
  elif [[ "${created_n}" -gt 0 ]]; then
    echo "  FAIL (${label}): resume re-ran stream (got 'created' event — double assistant header)"
    head -n 20 "${out}" || true
    failed=1
  elif [[ "${text_n}" -gt 0 ]]; then
    echo "  FAIL (${label}): resume re-ran stream (got text events — should only return final)"
    failed=1
  elif [[ "${lines_n}" -gt 1 ]]; then
    echo "  FAIL (${label}): resume returned ${lines_n} data lines (expected 1)"
    head -n 20 "${out}" || true
    failed=1
  fi

  if [[ "${KEEP_DEBUG}" != "1" ]]; then
    rm -f "${out}" "${hdrs}"
  fi
  return "${failed}"
}

echo "=== Resume reconnect test ==="

RESUME_FAIL=0
_check_resume "immediate" 0 || RESUME_FAIL=$((RESUME_FAIL + 1))
_check_resume "after_2s"  2 || RESUME_FAIL=$((RESUME_FAIL + 1))

if [[ "${RESUME_FAIL}" -gt 0 ]]; then
  echo "FAIL: ${RESUME_FAIL} resume check(s) failed"
  FAILURES=$((FAILURES + RESUME_FAIL))
else
  echo "PASS: both resume checks returned clean final-only response"
fi
echo ""

if [[ "${COMPARE_BACKBOARD}" == "1" ]]; then
  echo "=== Optional: direct Backboard compare ==="
  if [[ -z "${BACKBOARD_API_KEY}" || -z "${BACKBOARD_ASSISTANT_ID}" ]]; then
    echo "SKIP: set BACKBOARD_API_KEY and BACKBOARD_ASSISTANT_ID to compare."
  else
    BB_THREAD_STATUS="$(
      curl -sS -o "${BB_THREAD_BODY}" -w "%{http_code}" \
        -X POST \
        -H "X-API-Key: ${BACKBOARD_API_KEY}" \
        -H "Content-Type: application/json" \
        -d '{}' \
        "${BACKBOARD_BASE_URL}/assistants/${BACKBOARD_ASSISTANT_ID}/threads"
    )"
    if [[ "${BB_THREAD_STATUS}" != "200" ]]; then
      echo "SKIP: failed to create Backboard thread (HTTP ${BB_THREAD_STATUS})"
      cat "${BB_THREAD_BODY}" || true
    else
      BB_THREAD_ID="$(
        sed -n 's/.*"thread_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${BB_THREAD_BODY}" | head -n 1
      )"
      if [[ -z "${BB_THREAD_ID}" ]]; then
        echo "SKIP: could not parse Backboard thread_id"
      else
        echo "Backboard thread_id=${BB_THREAD_ID}"
        LLM_PROVIDER=""
        MODEL_NAME=""
        if [[ "${CHAT_MODEL}" == */* ]]; then
          LLM_PROVIDER="${CHAT_MODEL%%/*}"
          MODEL_NAME="${CHAT_MODEL#*/}"
        fi

        set +e
        if [[ -n "${LLM_PROVIDER}" && -n "${MODEL_NAME}" ]]; then
          curl -sS -N \
            --max-time "${STREAM_MAX_TIME}" \
            --trace-time \
            --trace-ascii "${BB_TRACE}" \
            -D "${BB_HEADERS}" \
            -X POST "${BACKBOARD_BASE_URL}/threads/${BB_THREAD_ID}/messages" \
            -H "X-API-Key: ${BACKBOARD_API_KEY}" \
            -F "stream=true" \
            -F "memory=Readonly" \
            -F "llm_provider=${LLM_PROVIDER}" \
            -F "model_name=${MODEL_NAME}" \
            -F "content=${PROMPT_TEXT}" \
            | perl -MTime::HiRes=time -ne 'printf("%.3f\t%s", time(), $_);' > "${BB_TIMED}"
        else
          curl -sS -N \
            --max-time "${STREAM_MAX_TIME}" \
            --trace-time \
            --trace-ascii "${BB_TRACE}" \
            -D "${BB_HEADERS}" \
            -X POST "${BACKBOARD_BASE_URL}/threads/${BB_THREAD_ID}/messages" \
            -H "X-API-Key: ${BACKBOARD_API_KEY}" \
            -F "stream=true" \
            -F "memory=Readonly" \
            -F "content=${PROMPT_TEXT}" \
            | perl -MTime::HiRes=time -ne 'printf("%.3f\t%s", time(), $_);' > "${BB_TIMED}"
        fi
        BB_CURL_EXIT=${PIPESTATUS[0]}
        set -e

        awk -v events_file="${BB_EVENTS}" '
          BEGIN {
            OFS="\t";
            print "idx", "ts", "line_len", "jump", "gap_sec" > events_file;
          }
          /"type"[[:space:]]*:[[:space:]]*"content_streaming"/ {
            split($0, parts, "\t");
            ts = parts[1];
            line = parts[2];
            n++;
            len=length(line);
            if (n>1) {
              jump=len-prev_len;
              gap=ts-prev_ts;
            } else {
              jump=0;
              gap=0;
            }
            print n, ts, len, jump, gap >> events_file;
            prev_len=len;
            prev_ts=ts;
          }
          END {
            print n+0;
          }
        ' "${BB_TIMED}" >/dev/null

        BB_RECV_BLOCKS="$(grep -c 'Recv data' "${BB_TRACE}" || true)"
        echo "Backboard curl_exit=${BB_CURL_EXIT} recv_blocks=${BB_RECV_BLOCKS}"
        print_event_snapshot "Timestamped Backboard content_streaming timeline" "${BB_EVENTS}"
        echo "Interpretation: if Backboard timeline is already bursty, root cause is upstream."
        echo "If Backboard is smooth but local SSE timeline is bursty, issue is in our API path."
      fi
    fi
  fi
  echo ""
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  echo ""
  echo "Cadence smoke test FAILED (${FAILURES} issue(s))."
  echo "Debug files:"
  echo "  ${SSE_OUT}"
  echo "  ${SSE_TIMED}"
  echo "  ${SSE_EVENTS}"
  echo "  ${SSE_TRACE}"
  echo "  ${SSE_HEADERS}"
  ls /tmp/nash-cadence-resume-*-"${TMP_ID}".txt 2>/dev/null | sed 's/^/  /' || true
  if [[ "${COMPARE_BACKBOARD}" == "1" ]]; then
    echo "  ${BB_TIMED}"
    echo "  ${BB_EVENTS}"
    echo "  ${BB_TRACE}"
    echo "  ${BB_HEADERS}"
  fi
  exit 1
fi

echo "Cadence smoke test PASSED."
echo "Debug files:"
echo "  ${SSE_OUT}"
echo "  ${SSE_TIMED}"
echo "  ${SSE_EVENTS}"
echo "  ${SSE_TRACE}"
echo "  ${SSE_HEADERS}"
ls /tmp/nash-cadence-resume-*-"${TMP_ID}".txt 2>/dev/null | sed 's/^/  /' || true
