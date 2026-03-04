#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# Smoke test: End-to-end document RAG through the LibreChat proxy
#
# Tests the complete proxy pipeline:
#   1. Upload a file to LibreChat's file endpoint
#   2. Send a chat completion through the proxy with the file attached
#   3. Verify the response references document content
##############################################################################

PROXY_URL="${PROXY_URL:-http://localhost:3080/api/backboard/v1}"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"

echo "=== Smoke: End-to-end doc RAG through proxy ==="
echo "    Proxy: ${PROXY_URL}"

# ---------- 1. Prepare a test document on disk ----------
echo ""
echo "--- Step 1: Create test document ---"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMPDIR="${PROJECT_ROOT}/images/temp/smoke-test"
mkdir -p "${TMPDIR}"
TMPFILE="${TMPDIR}/smoke001__test_upload_smoke.txt"
cat > "${TMPFILE}" <<'DOCEOF'
ZephyrTech Innovation Summit 2026 Agenda

Date: April 15-17, 2026
Location: Grand Hyatt, San Francisco

Keynote Speakers:
- Dr. Sarah Chen, CTO of ZephyrTech — "The Future of Quantum AI"
- Marcus Rivera, VP Engineering — "Building Resilient Distributed Systems"
- Professor Kim Nakamura, Stanford — "Ethics in Autonomous Decision Making"

Workshop Schedule:
Day 1: Foundation Track
  - 9am: Registration & Coffee
  - 10am: Keynote by Dr. Sarah Chen
  - 2pm: Hands-on Lab — Quantum Circuit Design

Day 2: Advanced Track
  - 9am: Marcus Rivera Keynote
  - 11am: Panel — Cloud-Native Architecture Patterns
  - 2pm: Hackathon Kickoff (theme: "AI for Climate")

Day 3: Leadership Track
  - 9am: Professor Nakamura Ethics Keynote
  - 11am: Fireside Chat with ZephyrTech CEO David Park
  - 3pm: Award Ceremony & Closing

Registration Fee: $2,500 per attendee
Expected Attendance: 3,500 participants
DOCEOF
echo "  Created: ${TMPFILE}"

# ---------- 2. Send chat completion with file reference ----------
echo ""
echo "--- Step 2: Send chat completion through proxy with document ---"

# Build file metadata header (mimics what initialize.ts does)
# filepath must be relative to project root (like images/temp/userId/fileId__name.txt)
REL_PATH="images/temp/smoke-test/smoke001__test_upload_smoke.txt"
FILE_META='[{"file_id":"smoke-test-001","filepath":"'"${REL_PATH}"'","filename":"test_upload_smoke.txt","type":"text/plain"}]'

RESP=$(curl -sS \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BB_KEY}" \
  -H "x-backboard-user-id: smoke-test-user" \
  -H "x-backboard-user-name: SmokeTest" \
  -H "x-backboard-files: ${FILE_META}" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Who are the keynote speakers and what is the registration fee?"}
    ],
    "stream": false
  }' \
  "${PROXY_URL}/chat/completions" 2>&1)

echo "Response (first 500 chars):"
echo "${RESP}" | head -c 500
echo ""

# ---------- 3. Verify document content in response ----------
echo ""
echo "--- Step 3: Verify RAG results ---"

FOUND_SPEAKER=false
FOUND_FEE=false

if echo "${RESP}" | grep -qi 'Sarah Chen\|Marcus Rivera\|Kim Nakamura'; then
  FOUND_SPEAKER=true
fi
if echo "${RESP}" | grep -qi '2,500\|2500'; then
  FOUND_FEE=true
fi

echo "  Keynote speakers found: ${FOUND_SPEAKER}"
echo "  Registration fee found: ${FOUND_FEE}"

if [[ "${FOUND_SPEAKER}" == "true" && "${FOUND_FEE}" == "true" ]]; then
  echo "PASS: Proxy RAG pipeline working end-to-end"
else
  echo "FAIL: Document content not retrieved through proxy"
  echo ""
  echo "Full response:"
  echo "${RESP}" | python3 -m json.tool 2>/dev/null || echo "${RESP}"
fi

# Cleanup
rm -f "${TMPFILE}"
echo ""
echo "Done."
