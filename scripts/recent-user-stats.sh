#!/usr/bin/env bash
# Show recently active users with token usage and last-seen datetime.
#
# Usage:
#   bash scripts/recent-user-stats.sh               # last 24h
#   bash scripts/recent-user-stats.sh --hours 48    # last 48h
#   bash scripts/recent-user-stats.sh --all         # all users
#
# Requires project .env with BACKBOARD_* credentials.

set -euo pipefail
cd "$(dirname "$0")/.."

HOURS=24
ALL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hours)
      [[ $# -ge 2 ]] || { echo "ERROR: --hours requires a value"; exit 1; }
      HOURS="$2"; shift 2 ;;
    --all)
      ALL=true; shift ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "ERROR: Unknown argument: $1"; exit 1 ;;
  esac
done

HOURS="$HOURS" ALL="$ALL" uv run python - <<'PY'
import os
from datetime import datetime, timezone, timedelta

from api.services.user_service import get_all_users
from api.routes.billing import get_user_plan, PLAN_TOKENS

hours = int(os.environ.get("HOURS", "24"))
show_all = os.environ.get("ALL", "false").lower() == "true"

cutoff = None if show_all else (datetime.now(timezone.utc) - timedelta(hours=hours))

users = get_all_users()

rows = []
for u in users:
    if u.get("active") is False:
        continue
    updated_raw = u.get("updatedAt", "")
    try:
        dt = datetime.fromisoformat(updated_raw.replace("Z", "+00:00")) if updated_raw else None
    except ValueError:
        dt = None

    if cutoff and (dt is None or dt < cutoff):
        continue

    plan = get_user_plan(u)
    limit = PLAN_TOKENS.get(plan, PLAN_TOKENS["free"])
    usage = int(u.get("tokenUsage", 0) or 0)

    rows.append({
        "name":    u.get("name") or u.get("username") or "(unknown)",
        "email":   u.get("email", ""),
        "plan":    "unlimited" if plan == "pro" else plan,
        "tokens":  usage,
        "limit":   limit,
        "updated": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "—",
        "dt":      dt or datetime.min.replace(tzinfo=timezone.utc),
    })

rows.sort(key=lambda r: r["dt"], reverse=True)

TITLE = f"  Nash — Active Users (last {hours}h)" if not show_all else "  Nash — All Users"
DIVIDER = "─" * 96

print()
print(TITLE)
print(DIVIDER)
print(f"  {'NAME':<22} {'EMAIL':<34} {'PLAN':<12} {'TOKENS':>10} {'/ LIMIT':>10}  {'LAST SEEN'}")
print(DIVIDER)

if not rows:
    print("  (no active users in window)")
else:
    for r in rows:
        pct = int(r["tokens"] / r["limit"] * 100) if r["limit"] else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        print(
            f"  {r['name']:<22.22} {r['email']:<34.34} {r['plan']:<12}"
            f" {r['tokens']:>10,} {r['limit']:>10,}  {r['updated']}"
        )

print(DIVIDER)
print(f"  {len(rows)} user(s)")
print()
PY
