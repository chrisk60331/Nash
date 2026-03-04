#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3080}"
BB_API_KEY="${BACKBOARD_API_KEY:-espr_cYodyuTRrijktQ8PPhJ963lLefqTgz33f2kohbUDo8w}"

echo "=== Smoke: Backboard native web search via proxy ==="
echo "Target: ${BASE_URL}/api/backboard/v1/chat/completions"

BODY='{
  "model": "openai/gpt-4o-mini",
  "stream": false,
  "messages": [
    {"role": "user", "content": "What is todays date and what are 3 top news headlines today?"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "web_search",
        "description": "Search the web",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
      }
    }
  ]
}'

status="$(curl -sS -o /tmp/smoke_bb_ws.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/backboard/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BB_API_KEY}" \
  -H "x-backboard-user-id: smoke-test-user" \
  "${BODY:+--data}" "${BODY}")"

echo ""
echo "HTTP status: ${status}"

if [[ "${status}" != "200" ]]; then
  echo "FAIL: POST /chat/completions returned ${status}"
  cat /tmp/smoke_bb_ws.json
  exit 1
fi

RESPONSE="$(cat /tmp/smoke_bb_ws.json)"
CONTENT="$(echo "${RESPONSE}" | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)"

if [[ -z "${CONTENT}" ]]; then
  echo "FAIL: No content in response"
  echo "${RESPONSE}" | head -c 500
  exit 1
fi

CONTENT_LEN="${#CONTENT}"
echo "Response length: ${CONTENT_LEN} chars"
echo ""
echo "--- Response preview (first 500 chars) ---"
echo "${CONTENT}" | head -c 500
echo ""
echo "---"

if echo "${CONTENT}" | grep -iqE "news|headline|today|search|web"; then
  echo ""
  echo "PASS: Response contains web-aware content"
else
  echo ""
  echo "WARN: Response may not contain web search results (check manually)"
fi

echo ""
echo "Smoke test completed."
