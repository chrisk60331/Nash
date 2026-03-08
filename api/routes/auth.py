import json
import logging
import httpx
from urllib.parse import urlencode

from flask import Blueprint, request, redirect, jsonify, make_response

from api.config import settings
from api.middleware.jwt_auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from api.middleware.rate_limit import limiter
from api.middleware.csrf import csrf_protect
from api.services import audit_service
from api.services import lockout_service
from api.services.user_service import find_user_by_email, find_user_by_id, create_user, update_user_field, verify_password
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.referral_service import (
    apply_referral_code_to_user,
    get_promo_code,
    redeem_promo_code,
    referral_code_exists,
)

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_CONFIG_MIGRATE_TYPES = {
    "thread_mapping", "conversation_meta",
    "prompt", "prompt_group", "user_favorites",
    "file_meta", "agent", "shared_link",
    "tag", "folder", "preset", "user_memory",
}


def _migrate_internal_memories(chat_assistant_id: str, config_assistant_id: str) -> None:
    """Copy internal memories from chat assistant to config assistant."""
    async def _do_migrate():
        client = get_client()
        response = await client.get_memories(chat_assistant_id)
        count = 0
        for m in response.memories:
            meta = m.metadata or {}
            mem_type = meta.get("type", "")
            if mem_type not in _CONFIG_MIGRATE_TYPES:
                continue
            await client.add_memory(
                assistant_id=config_assistant_id,
                content=m.content or "",
                metadata=meta,
            )
            count += 1
        logger.info("[auth] migrated %d internal memories from %s to %s", count, chat_assistant_id, config_assistant_id)

    try:
        run_async(_do_migrate())
    except Exception:
        logger.exception("Failed to migrate internal memories from %s to %s", chat_assistant_id, config_assistant_id)


def _ensure_bb_assistant(user: dict) -> str:
    """Ensure user has both a chat assistant and a config assistant."""
    existing = user.get("bbAssistantId", "")
    if not existing:
        async def _create_chat():
            client = get_client()
            assistant = await client.create_assistant(
                name=f"nash-user-{user['id'][:8]}",
                system_prompt="You are Nash, a helpful AI assistant. Be concise, accurate, and helpful.",
            )
            return str(assistant.assistant_id)

        existing = run_async(_create_chat())
        update_user_field(user, "bbAssistantId", existing)

    config_id = user.get("bbConfigAssistantId", "")
    needs_migration = False
    if not config_id:
        async def _create_config():
            client = get_client()
            assistant = await client.create_assistant(
                name=f"nash-config-{user['id'][:8]}",
                system_prompt="Internal config storage.",
            )
            return str(assistant.assistant_id)

        config_id = run_async(_create_config())
        update_user_field(user, "bbConfigAssistantId", config_id)
        needs_migration = True

    if not needs_migration:
        needs_migration = not user.get("bbConfigMigrated", False)

    if needs_migration:
        _migrate_internal_memories(existing, config_id)
        update_user_field(user, "bbConfigMigrated", True)

    return existing


@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        audit_service.emit("auth.login.failure", result="fail", reason="missing_fields")
        return jsonify({"message": "Email and password are required"}), 400

    if lockout_service.is_locked(email):
        remaining = lockout_service.lockout_remaining_seconds(email)
        audit_service.emit(
            "auth.login.locked",
            result="blocked",
            email_domain=email.split("@")[-1] if "@" in email else "",
            remaining_seconds=remaining,
        )
        return jsonify({"message": f"Account temporarily locked. Try again in {remaining // 60 + 1} minutes."}), 429

    user = find_user_by_email(email)
    if not user or not verify_password(user, password):
        became_locked = lockout_service.record_failure(email)
        audit_service.emit(
            "auth.login.failure",
            result="fail",
            reason="invalid_credentials",
            email_domain=email.split("@")[-1] if "@" in email else "",
            locked=became_locked,
        )
        if became_locked:
            audit_service.emit(
                "auth.login.locked",
                result="blocked",
                email_domain=email.split("@")[-1] if "@" in email else "",
                remaining_seconds=lockout_service.lockout_remaining_seconds(email),
            )
            return jsonify({"message": "Too many failed attempts. Account locked for 15 minutes."}), 429
        return jsonify({"message": "Incorrect email or password"}), 401

    lockout_service.record_success(email)
    _ensure_bb_assistant(user)

    user_id = user["id"]
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    audit_service.emit("auth.login.success", user_id=user_id)

    user_data = {
        "id": user["id"],
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "username": user.get("username", ""),
        "avatar": user.get("avatar", ""),
        "provider": user.get("provider", ""),
        "role": user.get("role", "USER"),
        "createdAt": user.get("createdAt", ""),
        "updatedAt": user.get("updatedAt", ""),
    }

    response = make_response(jsonify({"token": access_token, "user": user_data}))
    response.set_cookie(
        "refreshToken",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/api/auth/register", methods=["POST"])
@limiter.limit("5 per hour")
def register():
    if not settings.allow_registration:
        audit_service.emit("auth.register.failure", result="fail", reason="registration_disabled")
        return jsonify({"message": "Registration is disabled"}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    referral_code = (data.get("referralCode") or data.get("ref") or "").strip().upper()
    promo_code = (data.get("promoCode") or data.get("promo") or "").strip().upper()

    if not name or not email or not password:
        audit_service.emit("auth.register.failure", result="fail", reason="missing_fields")
        return jsonify({"message": "Name, email, and password are required"}), 400

    if len(password) < 8:
        audit_service.emit("auth.register.failure", result="fail", reason="password_too_short")
        return jsonify({"message": "Password must be at least 8 characters"}), 400

    existing = find_user_by_email(email)
    if existing:
        audit_service.emit("auth.register.failure", result="fail", reason="email_exists")
        return jsonify({"message": "A user with this email already exists"}), 409
    if referral_code and not referral_code_exists(referral_code):
        return jsonify({"message": "Referral code not found"}), 400
    if promo_code and get_promo_code(promo_code) is None:
        return jsonify({"message": "Promo code not found"}), 400

    user = create_user(
        email=email,
        name=name,
        provider="local",
        username=username,
        password=password,
    )

    _ensure_bb_assistant(user)

    if referral_code:
        apply_referral_code_to_user(user, referral_code)
    if promo_code:
        redeem_promo_code(user["id"], promo_code)

    audit_service.emit("auth.register.success", user_id=user["id"])

    refresh_token = create_refresh_token(user["id"])

    response = make_response(jsonify({"message": "Registration successful"}))
    response.set_cookie(
        "refreshToken",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/oauth/google", methods=["GET"])
@limiter.limit("20 per minute")
def oauth_google():
    audit_service.emit("auth.oauth.start", provider="google")
    callback_url = f"{settings.domain_server}{settings.google_callback_url}"
    referral_code = (request.args.get("ref") or "").strip().upper()
    promo_code = (request.args.get("promo") or "").strip().upper()
    state_payload = {
        "ref": referral_code or None,
        "promo": promo_code or None,
    }
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": json.dumps(state_payload),
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@auth_bp.route("/oauth/google/callback", methods=["GET"])
def oauth_google_callback():
    code = request.args.get("code")
    state = request.args.get("state") or "{}"
    if not code:
        return redirect(f"{settings.domain_client}/login?error=no_code")

    try:
        state_payload = json.loads(state)
    except json.JSONDecodeError:
        state_payload = {}
    referral_code = str(state_payload.get("ref") or "").strip().upper()
    promo_code = str(state_payload.get("promo") or "").strip().upper()

    callback_url = f"{settings.domain_server}{settings.google_callback_url}"
    token_resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": callback_url,
        "grant_type": "authorization_code",
    })
    if token_resp.status_code != 200:
        audit_service.emit("auth.oauth.failure", result="fail", provider="google", reason="token_exchange_failed")
        return redirect(f"{settings.domain_client}/login?error=token_exchange_failed")

    tokens = token_resp.json()
    google_access_token = tokens.get("access_token")

    userinfo_resp = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {google_access_token}"},
    )
    if userinfo_resp.status_code != 200:
        audit_service.emit("auth.oauth.failure", result="fail", provider="google", reason="userinfo_failed")
        return redirect(f"{settings.domain_client}/login?error=userinfo_failed")

    userinfo = userinfo_resp.json()
    email = userinfo.get("email", "")
    name = userinfo.get("name", email)
    picture = userinfo.get("picture", "")

    user = find_user_by_email(email)
    is_new_user = user is None
    if user is None:
        if not settings.allow_social_registration:
            audit_service.emit("auth.oauth.failure", result="fail", provider="google", reason="registration_disabled")
            return redirect(f"{settings.domain_client}/login?error=registration_disabled")
        user = create_user(
            email=email,
            name=name,
            avatar=picture,
            provider="google",
        )

    _ensure_bb_assistant(user)
    if not user.get("referredByUserId") and referral_code:
        try:
            apply_referral_code_to_user(user, referral_code)
        except ValueError:
            logger.warning("[auth] ignored invalid referral code during google login for %s", email)
    if promo_code:
        try:
            redeem_promo_code(user["id"], promo_code)
        except ValueError:
            logger.warning("[auth] ignored invalid promo code during google login for %s", email)

    user_id = user["id"]
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    audit_service.emit(
        "auth.oauth.success",
        user_id=user_id,
        provider="google",
        new_user=is_new_user,
    )

    redirect_url = f"{settings.domain_client}/c/new"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>SSO Login</title></head>
<body>
<script>
  try {{ sessionStorage.setItem('sso_token', {json.dumps(access_token)}); }} catch(e) {{}}
  window.location.replace("{redirect_url}");
</script>
<noscript><a href="{redirect_url}">Continue</a></noscript>
</body></html>"""

    response = make_response(html)
    response.set_cookie(
        "refreshToken",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/api/auth/refresh", methods=["GET", "POST"])
@limiter.limit("60 per minute")
@csrf_protect
def refresh():
    refresh_token = request.cookies.get("refreshToken")
    if not refresh_token:
        return jsonify({"token": "", "user": None})

    try:
        payload = decode_refresh_token(refresh_token)
    except Exception:
        audit_service.emit("auth.refresh.failure", result="fail", reason="invalid_token")
        return jsonify({"token": "", "user": None})

    user_id = payload.get("sub")
    if not user_id:
        audit_service.emit("auth.refresh.failure", result="fail", reason="missing_sub")
        return jsonify({"token": "", "user": None})
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    user = find_user_by_id(user_id)
    if user:
        _ensure_bb_assistant(user)
    user_data = None
    if user:
        user_data = {
            "id": user["id"],
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "username": user.get("username", ""),
            "avatar": user.get("avatar", ""),
            "provider": user.get("provider", ""),
            "role": user.get("role", "USER"),
            "createdAt": user.get("createdAt", ""),
            "updatedAt": user.get("updatedAt", ""),
        }

    audit_service.emit("auth.refresh.success", user_id=user_id)

    response = make_response(jsonify({"token": new_access_token, "user": user_data}))
    response.set_cookie(
        "refreshToken",
        new_refresh_token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/api/auth/logout", methods=["GET", "POST"])
@csrf_protect
def logout():
    # Best-effort: extract user_id from the refresh token cookie for the audit log.
    user_id = None
    try:
        rt = request.cookies.get("refreshToken")
        if rt:
            payload = decode_refresh_token(rt)
            user_id = payload.get("sub")
    except Exception:
        pass
    audit_service.emit("auth.logout", user_id=user_id)
    response = make_response(jsonify({"message": "Logged out"}))
    response.delete_cookie("refreshToken", path="/")
    return response
