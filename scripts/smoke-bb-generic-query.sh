#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# Smoke test: Generic vs specific queries for document search
#
# The user's actual failing prompt was "summarize this doc please" — a very
# generic query. Tests whether vague queries cause search_documents to fail.
##############################################################################

BB_URL="${BACKBOARD_BASE_URL:-https://app.backboard.io/api}"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"

hdr=(-H "X-API-Key: ${BB_KEY}")

echo "=== Smoke: Generic vs specific query for RAG ==="

# Setup
ASSISTANT=$(curl -sS "${hdr[@]}" -H "Content-Type: application/json" \
  -d '{"name":"smoke-generic-query","description":"test","instructions":"You answer questions about uploaded documents."}' \
  "${BB_URL}/assistants")
ASST=$(echo "${ASSISTANT}" | grep -o '"assistant_id":"[^"]*"' | head -1 | cut -d'"' -f4)

THREAD=$(curl -sS "${hdr[@]}" -H "Content-Type: application/json" -d '{}' "${BB_URL}/assistants/${ASST}/threads")
TID=$(echo "${THREAD}" | grep -o '"thread_id":"[^"]*"' | head -1 | cut -d'"' -f4)

TMPFILE=$(mktemp /tmp/test-XXXXXX.txt)
cat > "${TMPFILE}" <<'DOCEOF'
ACME Corp Q4 2025 Financial Results

Revenue: $8.3 billion (up 12% YoY)
Net Income: $1.7 billion
Operating Margin: 20.5%

CEO Jane Doe commented: "Our cloud division grew 34% this quarter,
driven by strong enterprise adoption of our AI platform."

Key metrics:
- Cloud ARR: $3.1 billion
- Total customers: 42,000
- Employee count: 15,200
- R&D spend: $1.2 billion (14.5% of revenue)
DOCEOF

DOC=$(curl -sS "${hdr[@]}" -F "file=@${TMPFILE};filename=acme_q4_results.txt" "${BB_URL}/threads/${TID}/documents")
rm -f "${TMPFILE}"
DID=$(echo "${DOC}" | grep -o '"document_id":"[^"]*"' | head -1 | cut -d'"' -f4)

for i in $(seq 1 20); do
  sleep 2
  S=$(curl -sS "${hdr[@]}" "${BB_URL}/documents/${DID}/status" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
  if [ "${S}" = "indexed" ]; then echo "Indexed in $((i*2))s"; break; fi
  if [ "${S}" = "failed" ]; then echo "FAILED"; exit 1; fi
done

echo ""
echo "--- Test 1: 'summarize this doc please' (generic, like user's failing query) ---"

PROXY_MSG='[System] You are Nash, an AI assistant. Never refer to yourself as LibreChat. Your name is Nash. The user'\''s name is Chris.

[Current Message]
summarize this doc please'

R1=$(curl -sS "${hdr[@]}" \
  -F "content=${PROXY_MSG}" \
  -F "stream=false" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-5.2" \
  "${BB_URL}/threads/${TID}/messages")

echo "${R1}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('Content:', d.get('content','')[:400])
tc = d.get('tool_calls',[])
tools = [t.get('function',{}).get('name','') for t in tc]
print('Tools:', tools)
"

if echo "${R1}" | grep -qi '8.3\|revenue\|ACME\|billion\|Jane Doe'; then
  echo "RESULT: PASS — doc content referenced"
else
  echo "RESULT: FAIL — doc content NOT found"
  echo "Full response:"
  echo "${R1}" | python3 -m json.tool 2>/dev/null || echo "${R1}"
fi

echo ""
echo "--- Test 2: 'what does the document say?' (another generic query) ---"
R2=$(curl -sS "${hdr[@]}" \
  -F "content=what does the document say?" \
  -F "stream=false" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-5.2" \
  "${BB_URL}/threads/${TID}/messages")

echo "${R2}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('Content:', d.get('content','')[:400])
tc = d.get('tool_calls',[])
tools = [t.get('function',{}).get('name','') for t in tc]
print('Tools:', tools)
"

if echo "${R2}" | grep -qi '8.3\|revenue\|ACME\|billion\|Jane Doe'; then
  echo "RESULT: PASS — doc content referenced"
else
  echo "RESULT: FAIL — doc content NOT found"
fi

# Assistants are never deleted
echo "  Assistant ${ASST} left intact"
echo ""
echo "Done."
