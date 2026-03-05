"""Token usage tracking and enforcement."""
from datetime import datetime, timezone

from api.services.user_service import find_user_by_id, update_user_field
from api.routes.billing import get_user_plan, PLAN_TOKENS


def _current_period_start() -> str:
    """Return the first day of the current month in UTC ISO format."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _ensure_period(user: dict) -> None:
    """Reset token usage if we've entered a new billing period."""
    period_start = _current_period_start()
    stored_reset = user.get("tokenUsageResetAt", "")
    if stored_reset != period_start:
        user["tokenUsage"] = 0
        user["tokenUsageResetAt"] = period_start
        update_user_field(user, "tokenUsage", 0)
        update_user_field(user, "tokenUsageResetAt", period_start)


def get_token_usage(user_id: str) -> dict:
    """Return current usage, limit, and remaining tokens for a user."""
    user = find_user_by_id(user_id)
    if not user:
        return {"usageTokens": 0, "includedTokens": 0, "tokensRemaining": 0}

    _ensure_period(user)
    plan = get_user_plan(user)
    limit = PLAN_TOKENS.get(plan, PLAN_TOKENS["free"])
    usage = int(user.get("tokenUsage", 0) or 0)
    remaining = max(0, limit - usage)

    return {
        "usageTokens": usage,
        "includedTokens": limit,
        "tokensRemaining": remaining,
    }


def check_token_limit(user_id: str) -> str | None:
    """Return an error message if the user has exceeded their token limit, else None."""
    info = get_token_usage(user_id)
    if info["tokensRemaining"] <= 0:
        return (
            f"You've used all {info['includedTokens']:,} tokens in your plan this month. "
            f"Upgrade your plan or wait until next month."
        )
    return None


def record_token_usage(user_id: str, tokens: int) -> None:
    """Add tokens to the user's monthly usage counter."""
    if tokens <= 0:
        return
    user = find_user_by_id(user_id)
    if not user:
        print(f"[token] WARN: user {user_id} not found, cannot record {tokens} tokens")
        return
    _ensure_period(user)
    prev = int(user.get("tokenUsage", 0) or 0)
    new_total = prev + tokens
    update_user_field(user, "tokenUsage", new_total)
    print(f"[token] recorded {tokens} tokens for {user.get('email')}: {prev} -> {new_total}")


def reset_token_usage(user_id: str) -> None:
    """Admin: reset a user's token usage to zero."""
    user = find_user_by_id(user_id)
    if not user:
        return
    update_user_field(user, "tokenUsage", 0)
    update_user_field(user, "tokenUsageResetAt", _current_period_start())
