"""Token usage tracking and enforcement."""

import os
import time
from datetime import datetime, timezone
from functools import lru_cache

import stripe
import yaml

from api.config import settings
from api.routes.billing import PLAN_TOKENS, get_user_plan
from api.services.balance_service import (
    get_balance_response,
    spend_token_credits,
    usd_to_token_credits,
)
from api.services.user_service import find_user_by_id, update_user_field

stripe.api_key = settings.stripe_secret_key


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
        user["meteredOverageReportedUnits"] = 0
        update_user_field(user, "tokenUsage", 0)
        update_user_field(user, "tokenUsageResetAt", period_start)
        update_user_field(user, "meteredOverageReportedUnits", 0)


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
    overage_tokens = max(0, usage - limit)

    return {
        "usageTokens": usage,
        "includedTokens": limit,
        "tokensRemaining": remaining,
        "overageTokens": overage_tokens,
        "overageEnabled": plan != "free",
    }


@lru_cache(maxsize=1)
def _load_model_pricing() -> dict[str, dict[str, float]]:
    yaml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "librechat.yaml",
    )
    try:
        with open(yaml_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}

    pricing = config.get("modelPricing", {})
    if not isinstance(pricing, dict):
        return {}

    normalized: dict[str, dict[str, float]] = {}
    for model_name, raw_pricing in pricing.items():
        if not isinstance(model_name, str) or not isinstance(raw_pricing, dict):
            continue
        normalized[model_name] = {
            "inputCostPer1mTokens": float(
                raw_pricing.get("inputCostPer1mTokens", 0) or 0
            ),
            "outputCostPer1mTokens": float(
                raw_pricing.get("outputCostPer1mTokens", 0) or 0
            ),
            "overageCostPer1mTokens": float(
                raw_pricing.get("overageCostPer1mTokens", 0) or 0
            ),
        }
    return normalized


def _get_model_token_prices_per_1m(model_name: str | None) -> tuple[float, float]:
    if not model_name:
        return 0.0, 0.0
    pricing = _load_model_pricing().get(model_name, {})
    input_cost = float(pricing.get("inputCostPer1mTokens", 0) or 0)
    output_cost = float(pricing.get("outputCostPer1mTokens", 0) or 0)
    return input_cost, output_cost


def _calculate_credit_charge_for_tokens(
    model_name: str | None,
    *,
    input_tokens: int,
    output_tokens: int,
) -> int:
    if input_tokens <= 0 and output_tokens <= 0:
        return 0

    input_cost_per_1m_tokens, output_cost_per_1m_tokens = (
        _get_model_token_prices_per_1m(model_name)
    )
    if input_cost_per_1m_tokens <= 0 and output_cost_per_1m_tokens <= 0:
        return 0

    usd_cost = (max(0, input_tokens) / 1_000_000) * input_cost_per_1m_tokens + (
        max(0, output_tokens) / 1_000_000
    ) * output_cost_per_1m_tokens
    return usd_to_token_credits(usd_cost)


def check_token_limit(user_id: str, model_name: str | None = None) -> str | None:
    """Return an error message if the user has exceeded their token limit and has no payment path."""
    info = get_token_usage(user_id)
    if info["tokensRemaining"] > 0:
        return None

    input_cost_per_1m_tokens, output_cost_per_1m_tokens = (
        _get_model_token_prices_per_1m(model_name)
    )
    if input_cost_per_1m_tokens <= 0 and output_cost_per_1m_tokens <= 0:
        return None

    balance = get_balance_response(user_id)
    if int(balance.get("tokenCredits", 0) or 0) > 0:
        return None

    user = find_user_by_id(user_id)
    if not user:
        return (
            f"You've used all {info['includedTokens']:,} tokens in your plan this month. "
            f"Upgrade your plan or wait until next month."
        )

    if user.get("stripeMeteredItemId", ""):
        return None

    return (
        "You've used all included tokens for this month and have no token credits left. "
        "Add credits, switch to a free model, or upgrade billing setup to continue."
    )


def _report_metered_overage_units(user: dict, plan: str, usage_total: int) -> None:
    included_tokens = PLAN_TOKENS.get(plan, PLAN_TOKENS["free"])
    overage_tokens = max(0, usage_total - included_tokens)
    chunk_size = max(1, settings.stripe_overage_tokens_per_unit)
    reportable_units = overage_tokens // chunk_size
    already_reported_units = int(user.get("meteredOverageReportedUnits", 0) or 0)
    delta_units = reportable_units - already_reported_units
    if delta_units <= 0:
        return

    subscription_item_id = user.get("stripeMeteredItemId", "")
    if not subscription_item_id:
        print(
            f"[token] WARN: user {user.get('email')} exceeded included usage but has no stripeMeteredItemId"
        )
        return

    try:
        stripe.SubscriptionItem.create_usage_record(
            subscription_item_id,
            quantity=delta_units,
            timestamp=int(time.time()),
            action="increment",
        )
        update_user_field(user, "meteredOverageReportedUnits", reportable_units)
        print(
            f"[token] reported {delta_units} metered overage units for {user.get('email')} "
            f"({overage_tokens} tokens over included usage)"
        )
    except Exception as exc:
        print(
            f"[token] WARN: failed to report metered overage for {user.get('email')}: {exc}"
        )


def record_token_usage(
    user_id: str,
    tokens: int,
    model_name: str | None = None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Add tokens to the user's monthly usage counter."""
    if tokens <= 0:
        return
    user = find_user_by_id(user_id)
    if not user:
        print(f"[token] WARN: user {user_id} not found, cannot record {tokens} tokens")
        return
    _ensure_period(user)
    plan = get_user_plan(user)
    prev = int(user.get("tokenUsage", 0) or 0)
    included_tokens = PLAN_TOKENS.get(plan, PLAN_TOKENS["free"])
    previous_overage_tokens = max(0, prev - included_tokens)
    new_total = prev + tokens
    update_user_field(user, "tokenUsage", new_total)

    current_overage_tokens = max(0, new_total - included_tokens)
    overage_tokens_delta = current_overage_tokens - previous_overage_tokens

    effective_input_tokens = max(0, input_tokens)
    effective_output_tokens = max(0, output_tokens)

    if effective_input_tokens <= 0 and effective_output_tokens <= 0:
        effective_input_tokens = overage_tokens_delta

    exact_total_tokens = effective_input_tokens + effective_output_tokens
    if (
        overage_tokens_delta > 0
        and exact_total_tokens > overage_tokens_delta
        and exact_total_tokens > 0
    ):
        scale = overage_tokens_delta / exact_total_tokens
        effective_input_tokens = int(round(effective_input_tokens * scale))
        effective_output_tokens = overage_tokens_delta - effective_input_tokens
    elif overage_tokens_delta > 0 and exact_total_tokens < overage_tokens_delta:
        effective_input_tokens += overage_tokens_delta - exact_total_tokens

    token_credit_charge = 0
    input_cost_per_1m_tokens = 0.0
    output_cost_per_1m_tokens = 0.0
    usd_charge = 0.0

    if overage_tokens_delta > 0:
        token_credit_charge = _calculate_credit_charge_for_tokens(
            model_name,
            input_tokens=effective_input_tokens,
            output_tokens=effective_output_tokens,
        )
        input_cost_per_1m_tokens, output_cost_per_1m_tokens = (
            _get_model_token_prices_per_1m(model_name)
        )

    available_token_credits = int(
        get_balance_response(user_id).get("tokenCredits", 0) or 0
    )
    if token_credit_charge > 0 and available_token_credits > 0:
        credits_to_spend = min(available_token_credits, token_credit_charge)
        usd_charge = credits_to_spend / max(1, settings.token_credits_per_usd)
        print(
            "[token] charged chat overage credits "
            f"user={user.get('email') or user_id} "
            f"model={model_name or '(unknown)'} "
            f"overage_tokens={overage_tokens_delta} "
            f"input_tokens={effective_input_tokens} "
            f"output_tokens={effective_output_tokens} "
            f"input_cost_per_1m={input_cost_per_1m_tokens} "
            f"output_cost_per_1m={output_cost_per_1m_tokens} "
            f"token_credits={credits_to_spend} "
            f"usd={usd_charge:.6f}"
        )
        spend_token_credits(
            user_id,
            token_credits=credits_to_spend,
            description="Applied token credits to chat overage",
            metadata={
                "source": "chat_overage",
                "model": model_name or "",
                "tokenUsageBefore": prev,
                "tokenUsageAfter": new_total,
                "overageTokens": overage_tokens_delta,
                "inputTokensCharged": effective_input_tokens,
                "outputTokensCharged": effective_output_tokens,
                "inputCostPer1mTokens": input_cost_per_1m_tokens,
                "outputCostPer1mTokens": output_cost_per_1m_tokens,
                "tokenCreditsCharged": credits_to_spend,
                "usdCharged": round(usd_charge, 6),
            },
        )

    remaining_credit_charge = max(0, token_credit_charge - available_token_credits)
    if overage_tokens_delta > 0 and remaining_credit_charge > 0 and plan != "free":
        if user.get("stripeMeteredItemId", ""):
            _report_metered_overage_units(user, plan, new_total)
        else:
            print(
                "[token] WARN: paid overage has no remaining payment path "
                f"user={user.get('email') or user_id} "
                f"model={model_name or '(unknown)'} "
                f"overage_tokens={overage_tokens_delta} "
                f"remaining_token_credit_charge={remaining_credit_charge}"
            )
    elif overage_tokens_delta > 0 and token_credit_charge <= 0 and plan != "free":
        _report_metered_overage_units(user, plan, new_total)

    print(
        f"[token] recorded {tokens} tokens for {user.get('email')}: {prev} -> {new_total}"
    )


def reset_token_usage(user_id: str) -> None:
    """Admin: reset a user's token usage to zero."""
    user = find_user_by_id(user_id)
    if not user:
        return
    update_user_field(user, "tokenUsage", 0)
    update_user_field(user, "tokenUsageResetAt", _current_period_start())
    update_user_field(user, "meteredOverageReportedUnits", 0)
