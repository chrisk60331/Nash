#!/usr/bin/env bash
# =============================================================================
# Regenerate librechat.yaml with live model data from Backboard.
# Paginates through all models (500 per page) for every provider.
#
# Usage:
#   BACKBOARD_API_KEY=espr_... ./scripts/regen-model-list.sh
# =============================================================================
set -euo pipefail

API_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"
BASE_URL="${BACKBOARD_BASE_URL:-https://app.backboard.io/api}"
PAGE_SIZE=500
YAML_OUT="librechat.yaml"

fetch_models() {
  local provider="$1"
  local skip=0
  local total=1
  local all_models=""

  while [[ $skip -lt $total ]]; do
    local resp
    resp=$(curl -sS -H "X-API-Key: ${API_KEY}" \
      "${BASE_URL}/models?provider=${provider}&model_type=llm&skip=${skip}&limit=${PAGE_SIZE}")

    total=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))")

    local page_models
    page_models=$(echo "$resp" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    if m.get('model_type') == 'llm':
        print(f\"{m['provider']}/{m['name']}\")
")
    if [[ -n "$page_models" ]]; then
      if [[ -n "$all_models" ]]; then
        all_models="${all_models}
${page_models}"
      else
        all_models="$page_models"
      fi
    fi
    skip=$((skip + PAGE_SIZE))
  done

  echo "$all_models" | sort
}

write_endpoint() {
  local name="$1"
  local provider="$2"
  local title_model="$3"
  local display_label="$4"

  echo "Fetching ${provider} models..." >&2
  local models
  models=$(fetch_models "$provider")
  local count
  count=$(echo "$models" | grep -c . || true)
  echo "  → ${count} LLM models" >&2

  cat <<ENDBLOCK
    - name: '${name}'
      apiKey: '\${BACKBOARD_API_KEY}'
      baseURL: 'http://localhost:3080/api/backboard/v1'
      models:
        default:
ENDBLOCK

  echo "$models" | while IFS= read -r m; do
    [[ -n "$m" ]] && echo "          - '${m}'"
  done

  cat <<ENDBLOCK
        fetch: false
      titleConvo: true
      titleModel: '${title_model}'
      modelDisplayLabel: '${display_label}'
ENDBLOCK
}

echo "Generating ${YAML_OUT} from live Backboard data..."

cat > "${YAML_OUT}" <<'HEADER'
version: 1.3.4
cache: true

interface:
  webSearch: true
  endpointsMenu: true
  modelSelect: true
  parameters: true
  sidePanel: true
  presets: true
  bookmarks: true
  agents:
    use: true
    create: true

speech:
  speechTab:
    textToSpeech: false
    speechToText: false

memory:
  disabled: false

registration:
  socialLogins: ['google']

endpoints:
  custom:
HEADER

write_endpoint "OpenAI"      "openai"      "openai/gpt-4o-mini"                                    "OpenAI"      >> "${YAML_OUT}"
write_endpoint "Anthropic"   "anthropic"   "anthropic/claude-sonnet-4-6"                           "Anthropic"   >> "${YAML_OUT}"
write_endpoint "Google"      "google"      "google/gemini-2.5-flash"                               "Google"      >> "${YAML_OUT}"
write_endpoint "xAI"         "xai"         "xai/grok-3-mini"                                      "xAI"         >> "${YAML_OUT}"
write_endpoint "OpenRouter"  "openrouter"  "openrouter/google/gemini-2.5-flash"                    "OpenRouter"  >> "${YAML_OUT}"
write_endpoint "Cohere"      "cohere"      "cohere/command-a-03-2025"                              "Cohere"      >> "${YAML_OUT}"
write_endpoint "Cerebras"    "cerebras"    "cerebras/meta-llama/llama-3.1-8b-instruct"             "Cerebras"    >> "${YAML_OUT}"
write_endpoint "AWS Bedrock" "aws-bedrock" "aws-bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0" "AWS Bedrock" >> "${YAML_OUT}"
write_endpoint "Featherless" "featherless" "featherless/0-hero/Matter-0.1-Slim-7B-C"               "Featherless" >> "${YAML_OUT}"

total_lines=$(wc -l < "${YAML_OUT}")
echo ""
echo "Done! ${YAML_OUT} regenerated (${total_lines} lines)"
