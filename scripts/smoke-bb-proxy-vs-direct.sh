#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# Smoke test: Compare proxy-style prompt vs direct prompt for RAG
#
# Isolates WHY the proxy fails to retrieve document content while
# direct API calls succeed. Tests three scenarios on the SAME thread:
#   A) Direct bare question (like the passing smoke test)
#   B) Proxy-style formatted prompt (like buildFirstMessagePrompt produces)
#   C) Direct bare question again (sanity check that search still works)
##############################################################################

BB_URL="${BACKBOARD_BASE_URL:-https://app.backboard.io/api}"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"

hdr=(-H "X-API-Key: ${BB_KEY}")

echo "=== Smoke: Proxy-style prompt vs direct prompt for RAG ==="

# ---------- Setup: assistant + thread + indexed doc ----------
echo ""
echo "--- Setup: Create assistant, thread, upload & index doc ---"
ASSISTANT=$(curl -sS "${hdr[@]}" \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-proxy-vs-direct","description":"test","instructions":"You answer questions about uploaded documents."}' \
  "${BB_URL}/assistants")
ASSISTANT_ID=$(echo "${ASSISTANT}" | grep -o '"assistant_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "  Assistant: ${ASSISTANT_ID}"

THREAD=$(curl -sS "${hdr[@]}" -H "Content-Type: application/json" -d '{}' "${BB_URL}/assistants/${ASSISTANT_ID}/threads")
THREAD_ID=$(echo "${THREAD}" | grep -o '"thread_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "  Thread: ${THREAD_ID}"

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

DOC_RESP=$(curl -sS "${hdr[@]}" -F "file=@${TMPFILE};filename=acme_q4_results.txt" "${BB_URL}/threads/${THREAD_ID}/documents")
rm -f "${TMPFILE}"
DOC_ID=$(echo "${DOC_RESP}" | grep -o '"document_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "  Document: ${DOC_ID}"

# Poll for indexing
for i in $(seq 1 20); do
  sleep 2
  STATUS=$(curl -sS "${hdr[@]}" "${BB_URL}/documents/${DOC_ID}/status" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
  if [ "${STATUS}" = "indexed" ]; then echo "  Indexed in $((i*2))s"; break; fi
  if [ "${STATUS}" = "failed" ]; then echo "  FAILED to index"; exit 1; fi
done

echo ""
echo "=========================================="
echo "  TEST A: Direct bare question"
echo "=========================================="
RESP_A=$(curl -sS "${hdr[@]}" \
  -F "content=What was ACME Corp's revenue in Q4 2025?" \
  -F "stream=false" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-4o-mini" \
  "${BB_URL}/threads/${THREAD_ID}/messages")

CONTENT_A=$(echo "${RESP_A}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('content','')[:300])" 2>/dev/null || echo "${RESP_A}" | head -c 300)
TOOLS_A=$(echo "${RESP_A}" | python3 -c "import json,sys;d=json.load(sys.stdin);tc=d.get('tool_calls',[]);print(json.dumps([t.get('function',{}).get('name','') for t in tc]))" 2>/dev/null || echo "unknown")
echo "  Content: ${CONTENT_A}"
echo "  Tools used: ${TOOLS_A}"

if echo "${RESP_A}" | grep -qi '8.3\|8,300\|8.3 billion'; then
  echo "  RESULT: PASS — found revenue"
else
  echo "  RESULT: FAIL — revenue not found"
fi

echo ""
echo "=========================================="
echo "  TEST B: Proxy-style formatted prompt"
echo "=========================================="
# This mimics exactly what buildFirstMessagePrompt produces
PROXY_PROMPT='[System] You are Nash, an AI assistant. Never refer to yourself as LibreChat. Your name is Nash. The user'\''s name is Chris.

[System Instructions]
You are ChatGPT, a large language model trained by OpenAI, based on the GPT-4 architecture.

[Current Message]
What was ACME Corp'\''s revenue in Q4 2025?'

RESP_B=$(curl -sS "${hdr[@]}" \
  -F "content=${PROXY_PROMPT}" \
  -F "stream=false" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-4o-mini" \
  "${BB_URL}/threads/${THREAD_ID}/messages")

CONTENT_B=$(echo "${RESP_B}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('content','')[:300])" 2>/dev/null || echo "${RESP_B}" | head -c 300)
TOOLS_B=$(echo "${RESP_B}" | python3 -c "import json,sys;d=json.load(sys.stdin);tc=d.get('tool_calls',[]);print(json.dumps([t.get('function',{}).get('name','') for t in tc]))" 2>/dev/null || echo "unknown")
echo "  Content: ${CONTENT_B}"
echo "  Tools used: ${TOOLS_B}"

if echo "${RESP_B}" | grep -qi '8.3\|8,300\|8.3 billion'; then
  echo "  RESULT: PASS — found revenue"
else
  echo "  RESULT: FAIL — revenue not found"
fi

echo ""
echo "=========================================="
echo "  TEST C: Proxy-style with model=gpt-5.2"
echo "  (the model the user was actually using)"
echo "=========================================="
RESP_C=$(curl -sS "${hdr[@]}" \
  -F "content=${PROXY_PROMPT}" \
  -F "stream=false" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-5.2" \
  "${BB_URL}/threads/${THREAD_ID}/messages")

CONTENT_C=$(echo "${RESP_C}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('content','')[:300])" 2>/dev/null || echo "${RESP_C}" | head -c 300)
TOOLS_C=$(echo "${RESP_C}" | python3 -c "import json,sys;d=json.load(sys.stdin);tc=d.get('tool_calls',[]);print(json.dumps([t.get('function',{}).get('name','') for t in tc]))" 2>/dev/null || echo "unknown")
echo "  Content: ${CONTENT_C}"
echo "  Tools used: ${TOOLS_C}"

if echo "${RESP_C}" | grep -qi '8.3\|8,300\|8.3 billion'; then
  echo "  RESULT: PASS — found revenue"
else
  echo "  RESULT: FAIL — revenue not found"
fi

echo ""
echo "=========================================="
echo "  TEST D: Direct bare question (sanity)"
echo "=========================================="
RESP_D=$(curl -sS "${hdr[@]}" \
  -F "content=What is the cloud ARR?" \
  -F "stream=false" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-4o-mini" \
  "${BB_URL}/threads/${THREAD_ID}/messages")

CONTENT_D=$(echo "${RESP_D}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('content','')[:300])" 2>/dev/null || echo "${RESP_D}" | head -c 300)
TOOLS_D=$(echo "${RESP_D}" | python3 -c "import json,sys;d=json.load(sys.stdin);tc=d.get('tool_calls',[]);print(json.dumps([t.get('function',{}).get('name','') for t in tc]))" 2>/dev/null || echo "unknown")
echo "  Content: ${CONTENT_D}"
echo "  Tools used: ${TOOLS_D}"

if echo "${RESP_D}" | grep -qi '3.1\|3,100\|3.1 billion'; then
  echo "  RESULT: PASS — found Cloud ARR"
else
  echo "  RESULT: FAIL — Cloud ARR not found"
fi

# ---------- Done ----------
echo ""
echo "--- Done ---"
echo "  Assistant ${ASSISTANT_ID} left intact (never delete assistants)"

echo ""
echo "=== Summary ==="
echo "  A (direct/gpt-4o-mini): revenue check"
echo "  B (proxy-format/gpt-4o-mini): revenue check"
echo "  C (proxy-format/gpt-5.2): revenue check"
echo "  D (direct/gpt-4o-mini): cloud ARR check"
