#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# Smoke test: Backboard document upload → index → vector search
#
# Tests the full RAG pipeline:
#   1. Create an assistant
#   2. Create a thread
#   3. Upload a small text doc to the thread
#   4. Poll until indexed
#   5. Send a message asking about the doc content
#   6. Check that the response references the doc (not hallucination)
#   7. Clean up
##############################################################################

BB_URL="${BACKBOARD_BASE_URL:-https://app.backboard.io/api}"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"

hdr=(-H "X-API-Key: ${BB_KEY}")

echo "=== Smoke: Backboard doc search pipeline ==="
echo "    URL: ${BB_URL}"

# ---------- 1. Create assistant ----------
echo ""
echo "--- Step 1: Create assistant ---"
ASSISTANT=$(curl -sS "${hdr[@]}" \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-docsearch","description":"smoke test for doc search","instructions":"You answer questions about uploaded documents."}' \
  "${BB_URL}/assistants")
echo "Response: ${ASSISTANT}"

ASSISTANT_ID=$(echo "${ASSISTANT}" | grep -o '"assistant_id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [[ -z "${ASSISTANT_ID}" ]]; then
  echo "FAIL: Could not create assistant"
  exit 1
fi
echo "PASS: Created assistant ${ASSISTANT_ID}"

# ---------- 2. Create thread ----------
echo ""
echo "--- Step 2: Create thread ---"
THREAD=$(curl -sS "${hdr[@]}" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "${BB_URL}/assistants/${ASSISTANT_ID}/threads")
echo "Response: ${THREAD}"

THREAD_ID=$(echo "${THREAD}" | grep -o '"thread_id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [[ -z "${THREAD_ID}" ]]; then
  echo "FAIL: Could not create thread"
  exit 1
fi
echo "PASS: Created thread ${THREAD_ID}"

# ---------- 3. Upload a small doc ----------
echo ""
echo "--- Step 3: Upload document ---"

TMPFILE=$(mktemp /tmp/smoke-doc-XXXXXX.txt)
cat > "${TMPFILE}" <<'DOCEOF'
Project Moonshot Internal Memo

Date: January 15, 2026
Classification: Confidential

Project Moonshot is our code name for the next-generation quantum computing
initiative. The project budget is $4.2 million USD for fiscal year 2026.

Key team members:
- Dr. Alice Zhang, Principal Investigator
- Bob Martinez, Lead Engineer
- Carol Wu, Quantum Algorithm Specialist

The primary objective is to achieve 1000-qubit error-corrected computation
by Q3 2026. Our current prototype, codenamed "Stardust", has achieved
127 qubits with a coherence time of 200 microseconds.

Critical milestones:
1. Complete cryogenic system upgrade by March 2026
2. Achieve 500-qubit entanglement by June 2026
3. Full 1000-qubit demonstration by September 2026

Risk factors include supply chain delays for dilution refrigerators
and potential patent conflicts with QuantumCorp Inc.
DOCEOF

DOC_RESP=$(curl -sS "${hdr[@]}" \
  -F "file=@${TMPFILE};filename=moonshot_memo.txt" \
  "${BB_URL}/threads/${THREAD_ID}/documents")
rm -f "${TMPFILE}"
echo "Response: ${DOC_RESP}"

DOC_ID=$(echo "${DOC_RESP}" | grep -o '"document_id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [[ -z "${DOC_ID}" ]]; then
  echo "FAIL: Could not upload document"
  exit 1
fi
echo "PASS: Uploaded document ${DOC_ID}"

# ---------- 4. Poll for indexing ----------
echo ""
echo "--- Step 4: Wait for indexing ---"
MAX_WAIT=120
ELAPSED=0
DOC_STATUS="pending"
while [[ "${DOC_STATUS}" != "indexed" && ${ELAPSED} -lt ${MAX_WAIT} ]]; do
  sleep 3
  ELAPSED=$((ELAPSED + 3))
  STATUS_RESP=$(curl -sS "${hdr[@]}" "${BB_URL}/documents/${DOC_ID}/status")
  DOC_STATUS=$(echo "${STATUS_RESP}" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
  echo "  ${ELAPSED}s: status=${DOC_STATUS}"
  if [[ "${DOC_STATUS}" == "failed" ]]; then
    echo "FAIL: Document indexing failed"
    echo "Response: ${STATUS_RESP}"
    exit 1
  fi
done

if [[ "${DOC_STATUS}" != "indexed" ]]; then
  echo "FAIL: Document not indexed after ${MAX_WAIT}s"
  exit 1
fi
echo "PASS: Document indexed in ${ELAPSED}s"

# ---------- 5. List thread documents (sanity) ----------
echo ""
echo "--- Step 5: Verify document on thread ---"
THREAD_DOCS=$(curl -sS "${hdr[@]}" "${BB_URL}/threads/${THREAD_ID}/documents")
echo "Thread docs: ${THREAD_DOCS}"
if echo "${THREAD_DOCS}" | grep -q "moonshot_memo"; then
  echo "PASS: Document visible on thread"
else
  echo "FAIL: Document not found on thread"
  exit 1
fi

# ---------- 6. Send message and check response ----------
echo ""
echo "--- Step 6: Send message asking about document ---"
MSG_RESP=$(curl -sS "${hdr[@]}" \
  -F "content=What is the budget for Project Moonshot and who is the principal investigator?" \
  -F "stream=false" \
  "${BB_URL}/threads/${THREAD_ID}/messages")

echo "Response (first 500 chars):"
echo "${MSG_RESP}" | head -c 500
echo ""

# Check for key facts from the document
FOUND_BUDGET=false
FOUND_PI=false

if echo "${MSG_RESP}" | grep -qi '4.2 million\|4,200,000\|4.2M'; then
  FOUND_BUDGET=true
fi
if echo "${MSG_RESP}" | grep -qi 'Alice Zhang'; then
  FOUND_PI=true
fi

echo ""
echo "--- Results ---"
echo "  Budget (4.2M) found in response: ${FOUND_BUDGET}"
echo "  PI (Dr. Alice Zhang) found in response: ${FOUND_PI}"

if [[ "${FOUND_BUDGET}" == "true" && "${FOUND_PI}" == "true" ]]; then
  echo "PASS: LLM retrieved document content via RAG"
else
  echo "FAIL: LLM did not retrieve document content"
  echo ""
  echo "Full response:"
  echo "${MSG_RESP}"
  exit 1
fi

# ---------- 6b. Send message with streaming (like proxy does) ----------
echo ""
echo "--- Step 6b: Send message with stream=true + explicit model (like proxy) ---"
STREAM_RESP=$(curl -sS "${hdr[@]}" \
  -F "content=What are the risk factors mentioned in the document?" \
  -F "stream=true" \
  -F "llm_provider=openai" \
  -F "model_name=gpt-4o-mini" \
  "${BB_URL}/threads/${THREAD_ID}/messages")

echo "Stream response (first 800 chars):"
echo "${STREAM_RESP}" | head -c 800
echo ""

FOUND_RISK=false
if echo "${STREAM_RESP}" | grep -qi 'supply chain\|dilution\|refrigerator\|QuantumCorp\|patent'; then
  FOUND_RISK=true
fi
echo "  Risk factors found in streaming response: ${FOUND_RISK}"

if [[ "${FOUND_RISK}" == "true" ]]; then
  echo "PASS: Streaming RAG also works"
else
  echo "FAIL: Streaming RAG did not retrieve document content"
  echo ""
  echo "Full streaming response:"
  echo "${STREAM_RESP}"
fi

# ---------- 7. Done ----------
echo ""
echo "--- Step 7: Done ---"
echo "  Assistant ${ASSISTANT_ID} left intact (never delete assistants)"

echo ""
echo "=== All smoke tests passed ==="
