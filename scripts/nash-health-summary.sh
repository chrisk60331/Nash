#!/usr/bin/env bash
# Nash tmux dashboard — Health & Growth Summary
#
# Sections:
#   1. CloudWatch error/warn digest  (last 1h by default)
#   2. New user signups              (last 7 days by default)
#   3. Stripe billing events         (last 20 events)
#
# Usage:
#   bash scripts/nash-health-summary.sh               # dev, 1h errors, 7d signups
#   bash scripts/nash-health-summary.sh prod          # prod env
#   ENV=prod ERROR_HOURS=2 SIGNUP_DAYS=14 bash scripts/nash-health-summary.sh
#
# Requires: .env with BACKBOARD_* + STRIPE_SECRET_KEY, AWS CLI with App Runner access

set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="nash"
AWS_REGION="${AWS_REGION:-us-west-2}"
ENV="${1:-${ENV:-dev}}"
ERROR_HOURS="${ERROR_HOURS:-1}"
SIGNUP_DAYS="${SIGNUP_DAYS:-7}"

# ── Resolve App Runner log group ─────────────────────────────────────────────
SERVICE_NAME="${APP_NAME}-${ENV}"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")"
SERVICE_ARN="$(aws apprunner list-services --region "${AWS_REGION}" \
  --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn | [0]" --output text)"
SERVICE_ID="$(echo "${SERVICE_ARN}" | awk -F'/' '{print $NF}')"
LOG_GROUP="/aws/apprunner/${SERVICE_NAME}/${SERVICE_ID}/service"

USER_LIMIT=5
# ── Run all three sections in one Python process ──────────────────────────────
LOG_GROUP="${LOG_GROUP:-}" \
AWS_REGION="${AWS_REGION}" \
ERROR_HOURS="${ERROR_HOURS}" \
SIGNUP_DAYS="${SIGNUP_DAYS}" \
USER_LIMIT="${USER_LIMIT}" \
ENV="${ENV}" \
uv run python - <<'PY'
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

import stripe

from api.config import settings
from api.services.user_service import get_all_users
from api.routes.billing import get_user_plan

stripe.api_key = settings.stripe_secret_key

LOG_GROUP   = os.environ.get("LOG_GROUP", "")
AWS_REGION  = os.environ.get("AWS_REGION", "us-west-2")
ERROR_HOURS = int(os.environ.get("ERROR_HOURS", "1"))
SIGNUP_DAYS = int(os.environ.get("SIGNUP_DAYS", "7"))
ENV         = os.environ.get("ENV", "dev")
USER_LIMIT  = int(os.environ.get("USER_LIMIT", "100"))
W = 96
DIV = "─" * W
now_utc = datetime.now(timezone.utc)

def ts(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "—"

def parse_dt(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None

# ── Header ────────────────────────────────────────────────────────────────────
print()
print(f"  Nash [{ENV}] — Health & Growth Summary   {ts(now_utc)}")
print(DIV)


# ══ SECTION 1: CloudWatch error/warn digest ════════════════════════════════════
print(f"\n  ERRORS / WARNINGS  (last {ERROR_HOURS}h)\n")

if not LOG_GROUP:
    print("  (skipped — log group not resolved)")
else:
    start_ms = int((now_utc - timedelta(hours=ERROR_HOURS)).timestamp() * 1000)
    try:
        result = subprocess.run(
            [
                "aws", "logs", "filter-log-events",
                "--log-group-name", LOG_GROUP,
                "--region", AWS_REGION,
                "--start-time", str(start_ms),
                "--filter-pattern", "?ERROR ?WARN ?FAIL",
                "--output", "json",
            ],
            capture_output=True, text=True, timeout=20,
        )
        events = json.loads(result.stdout or "{}").get("events", [])
    except Exception as exc:
        events = []
        print(f"  (CloudWatch query failed: {exc})")

    # Categorise by leading tag
    buckets: dict[str, list[str]] = {}
    for ev in events:
        msg = ev.get("message", "").strip()
        # Extract leading bracket-tag if present e.g. [token], [admin_users]
        tag = "OTHER"
        if msg.startswith("["):
            end = msg.find("]")
            if end != -1:
                tag = msg[: end + 1]
        elif "ERROR" in msg:
            tag = "ERROR"
        elif "FAIL" in msg:
            tag = "FAIL"
        elif "WARN" in msg:
            tag = "WARN"
        buckets.setdefault(tag, []).append(msg)

    if not buckets:
        print("  (no errors or warnings in window)")
    else:
        sorted_buckets = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        print(f"  {'TAG':<20} {'COUNT':>6}  LAST MESSAGE")
        print(f"  {'─'*20} {'─'*6}  {'─'*50}")
        for tag, msgs in sorted_buckets:
            last = msgs[-1][:70].replace("\n", " ")
            print(f"  {tag:<20} {len(msgs):>6}  {last}")


# ══ SECTION 2: New signups ═════════════════════════════════════════════════════
print(f"\n{DIV}\n  NEW SIGNUPS  (last {SIGNUP_DAYS}d)\n")

cutoff = now_utc - timedelta(days=SIGNUP_DAYS)
users = get_all_users()

new_users = []
for u in users:
    if u.get("active") is False:
        continue
    dt = parse_dt(u.get("createdAt", ""))
    if dt and dt >= cutoff:
        new_users.append((dt, u))

new_users.sort(key=lambda x: x[0], reverse=True)

if not new_users:
    print(f"  (no new signups in last {SIGNUP_DAYS} days)")
else:
    print(f"  {'NAME':<24} {'EMAIL':<34} {'PLAN':<10}  SIGNED UP")
    print(f"  {'─'*24} {'─'*34} {'─'*10}  {'─'*22}")
    for dt, u in new_users[:USER_LIMIT]:
        plan = get_user_plan(u)
        display_plan = "unlimited" if plan == "pro" else plan
        name  = (u.get("name") or u.get("username") or "(unknown)")[:24]
        email = u.get("email", "")[:34]
        print(f"  {name:<24} {email:<34} {display_plan:<10}  {ts(dt)}")

print(f"\n  {len(new_users)} signup(s)")


# ══ SECTION 3: Stripe billing events ══════════════════════════════════════════
print(f"\n{DIV}\n  STRIPE BILLING EVENTS  (last 20)\n")

BILLING_TYPES = {
    "customer.subscription.created",
    "customer.subscription.deleted",
    "customer.subscription.updated",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "invoice.payment_action_required",
}

try:
    all_events = stripe.Event.list(limit=50)
    billing_events = [e for e in all_events.auto_paging_iter()
                      if e["type"] in BILLING_TYPES][:20]
except Exception as exc:
    billing_events = []
    print(f"  (Stripe query failed: {exc})")

if not billing_events:
    print("  (no recent billing events)")
else:
    print(f"  {'DATETIME':<22} {'EVENT TYPE':<40} CUSTOMER")
    print(f"  {'─'*22} {'─'*40} {'─'*30}")
    for ev in billing_events:
        ev_dt = datetime.fromtimestamp(ev["created"], tz=timezone.utc)
        ev_type = ev["type"]
        obj = ev["data"]["object"]
        # Best-effort customer identifier
        customer = (
            obj.get("customer_email")
            or obj.get("customer_name")
            or obj.get("customer")
            or "—"
        )
        print(f"  {ts(ev_dt):<22} {ev_type:<40} {str(customer)[:30]}")


# ── Footer ────────────────────────────────────────────────────────────────────
print(f"\n{DIV}")
print()
PY
