#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage:
  bash scripts/reset-user-token-usage.sh --email user@example.com
  bash scripts/reset-user-token-usage.sh --user-id USER_ID

Resets the target user's monthly token usage to zero using the existing API services.
Requires a valid project `.env` so `uv run python` can load Backboard credentials.
EOF
}

identifier_type=""
identifier_value=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)
      [[ $# -ge 2 ]] || { echo "ERROR: --email requires a value"; exit 1; }
      [[ -z "$identifier_type" ]] || { echo "ERROR: Provide only one of --email or --user-id"; exit 1; }
      identifier_type="email"
      identifier_value="$2"
      shift 2
      ;;
    --user-id)
      [[ $# -ge 2 ]] || { echo "ERROR: --user-id requires a value"; exit 1; }
      [[ -z "$identifier_type" ]] || { echo "ERROR: Provide only one of --email or --user-id"; exit 1; }
      identifier_type="user_id"
      identifier_value="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$identifier_type" || -z "$identifier_value" ]]; then
  echo "ERROR: You must provide exactly one identifier."
  usage
  exit 1
fi

IDENTIFIER_TYPE="$identifier_type" IDENTIFIER_VALUE="$identifier_value" uv run python - <<'PY'
import os
import sys

from api.services.token_service import get_token_usage, reset_token_usage
from api.services.user_service import find_user_by_email, find_user_by_id


identifier_type = os.environ["IDENTIFIER_TYPE"]
identifier_value = os.environ["IDENTIFIER_VALUE"].strip()

if identifier_type == "email":
    user = find_user_by_email(identifier_value)
elif identifier_type == "user_id":
    user = find_user_by_id(identifier_value)
else:
    print(f"ERROR: Unsupported identifier type: {identifier_type}")
    sys.exit(1)

if not user:
    print(f"ERROR: User not found for {identifier_type}={identifier_value}")
    sys.exit(1)

user_id = user["id"]
before_usage = get_token_usage(user_id)
before_reset_at = user.get("tokenUsageResetAt", "")
before_overage_units = int(user.get("meteredOverageReportedUnits", 0) or 0)

reset_token_usage(user_id)

updated_user = find_user_by_id(user_id)
if not updated_user:
    print(f"ERROR: User disappeared after reset: {user_id}")
    sys.exit(1)

after_usage = get_token_usage(user_id)
after_reset_at = updated_user.get("tokenUsageResetAt", "")
after_overage_units = int(updated_user.get("meteredOverageReportedUnits", 0) or 0)

print("Token usage reset complete.")
print(f"User ID: {user_id}")
print(f"Email: {updated_user.get('email', '')}")
print(
    "Before:"
    f" usageTokens={before_usage['usageTokens']}"
    f" includedTokens={before_usage['includedTokens']}"
    f" overageTokens={before_usage['overageTokens']}"
    f" tokenUsageResetAt={before_reset_at or '(empty)'}"
    f" meteredOverageReportedUnits={before_overage_units}"
)
print(
    "After:"
    f" usageTokens={after_usage['usageTokens']}"
    f" includedTokens={after_usage['includedTokens']}"
    f" overageTokens={after_usage['overageTokens']}"
    f" tokenUsageResetAt={after_reset_at or '(empty)'}"
    f" meteredOverageReportedUnits={after_overage_units}"
)
PY
