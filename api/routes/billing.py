import stripe
from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.config import settings
from api.services.user_service import find_user_by_id

billing_bp = Blueprint("billing", __name__)

stripe.api_key = settings.stripe_secret_key

PLAN_TOKENS = {
    "free": settings.free_included_tokens,
    "plus": settings.plus_included_tokens,
    "pro": settings.pro_included_tokens,
}

PLAN_PRICE_IDS = {
    "plus": settings.stripe_price_id_plus,
    "pro": settings.stripe_price_id_unlimited,
}

PRICE_ID_TO_PLAN = {v: k for k, v in PLAN_PRICE_IDS.items()}


def get_user_plan(user: dict | None) -> str:
    if not user:
        return "free"
    stored = user.get("plan", "")
    if stored == "unlimited":
        stored = "pro"
    if stored in PLAN_TOKENS:
        return stored
    # ADMINs without an explicit plan default to pro
    if user.get("role", "").upper() == "ADMIN":
        return "pro"
    return "free"


@billing_bp.route("/api/billing/subscription", methods=["GET"])
@require_jwt
def get_subscription():
    from api.services.token_service import get_token_usage
    user = find_user_by_id(g.user_id)
    plan = get_user_plan(user)
    usage = get_token_usage(g.user_id)

    display_plan = "unlimited" if plan == "pro" else plan
    return jsonify({
        "subscription": display_plan if plan != "free" else None,
        "plan": display_plan,
        "status": "active",
        "usageTokens": usage["usageTokens"],
        "tokensRemaining": usage["tokensRemaining"],
        "includedTokens": usage["includedTokens"],
    })


@billing_bp.route("/api/billing/checkout", methods=["POST"])
@require_jwt
def create_checkout():
    data = request.get_json() or {}
    price_id = data.get("priceId", settings.stripe_price_id_plus)

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.domain_client}/c/new?checkout=success",
            cancel_url=f"{settings.domain_client}/c/new?checkout=cancel",
            client_reference_id=g.user_id,
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/api/billing/portal", methods=["POST"])
@require_jwt
def create_portal():
    user = find_user_by_id(g.user_id)
    customer_id = (user or {}).get("stripeCustomerId")
    if not customer_id:
        return jsonify({"error": "No billing account found"}), 400

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{settings.domain_client}/c/new",
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/api/billing/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception:
        return jsonify({"error": "Invalid webhook"}), 400

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        user_id = data_obj.get("client_reference_id")
        subscription_id = data_obj.get("subscription")
        customer_id = data_obj.get("customer")
        if user_id and subscription_id:
            from api.services.user_service import update_user_field
            user = find_user_by_id(user_id)
            if user:
                sub = stripe.Subscription.retrieve(subscription_id)
                price_id = sub["items"]["data"][0]["price"]["id"]
                plan = PRICE_ID_TO_PLAN.get(price_id, "plus")
                update_user_field(user, "plan", plan)
                update_user_field(user, "stripeCustomerId", customer_id)
                update_user_field(user, "stripeSubscriptionId", subscription_id)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub_status = data_obj.get("status", "")
        customer_id = data_obj.get("customer")
        if sub_status in ("canceled", "unpaid", "past_due"):
            from api.services.user_service import get_all_users, update_user_field
            for u in get_all_users():
                if u.get("stripeCustomerId") == customer_id:
                    update_user_field(u, "plan", "free")
                    break

    return jsonify({"received": True})
