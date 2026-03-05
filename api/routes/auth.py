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
from api.services.user_service import find_user_by_email, find_user_by_id, create_user, update_user_field, verify_password
from api.services.backboard_service import get_client
from api.services.async_runner import run_async

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
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = find_user_by_email(email)
    if not user or not verify_password(user, password):
        return jsonify({"message": "Incorrect email or password"}), 401

    _ensure_bb_assistant(user)

    user_id = user["id"]
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

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
        secure=False,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    if not settings.allow_registration:
        return jsonify({"message": "Registration is disabled"}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"message": "Name, email, and password are required"}), 400

    if len(password) < 8:
        return jsonify({"message": "Password must be at least 8 characters"}), 400

    existing = find_user_by_email(email)
    if existing:
        return jsonify({"message": "A user with this email already exists"}), 409

    user = create_user(
        email=email,
        name=name,
        provider="local",
        username=username,
        password=password,
    )

    _ensure_bb_assistant(user)

    refresh_token = create_refresh_token(user["id"])

    response = make_response(jsonify({"message": "Registration successful"}))
    response.set_cookie(
        "refreshToken",
        refresh_token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/oauth/google", methods=["GET"])
def oauth_google():
    callback_url = f"{settings.domain_server}{settings.google_callback_url}"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@auth_bp.route("/oauth/google/callback", methods=["GET"])
def oauth_google_callback():
    code = request.args.get("code")
    if not code:
        return redirect(f"{settings.domain_client}/login?error=no_code")

    callback_url = f"{settings.domain_server}{settings.google_callback_url}"
    token_resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": callback_url,
        "grant_type": "authorization_code",
    })
    if token_resp.status_code != 200:
        return redirect(f"{settings.domain_client}/login?error=token_exchange_failed")

    tokens = token_resp.json()
    google_access_token = tokens.get("access_token")

    userinfo_resp = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {google_access_token}"},
    )
    if userinfo_resp.status_code != 200:
        return redirect(f"{settings.domain_client}/login?error=userinfo_failed")

    userinfo = userinfo_resp.json()
    email = userinfo.get("email", "")
    name = userinfo.get("name", email)
    picture = userinfo.get("picture", "")

    user = find_user_by_email(email)
    if user is None:
        if not settings.allow_social_registration:
            return redirect(f"{settings.domain_client}/login?error=registration_disabled")
        user = create_user(
            email=email,
            name=name,
            avatar=picture,
            provider="google",
        )

    _ensure_bb_assistant(user)

    user_id = user["id"]
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

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
        secure=False,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/api/auth/refresh", methods=["GET", "POST"])
def refresh():
    refresh_token = request.cookies.get("refreshToken")
    if not refresh_token:
        return jsonify({"token": "", "user": None})

    try:
        payload = decode_refresh_token(refresh_token)
    except Exception:
        return jsonify({"token": "", "user": None})

    user_id = payload["sub"]
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

    response = make_response(jsonify({"token": new_access_token, "user": user_data}))
    response.set_cookie(
        "refreshToken",
        new_refresh_token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=settings.jwt_refresh_expiry_seconds,
        path="/",
    )
    return response


@auth_bp.route("/api/auth/logout", methods=["GET", "POST"])
def logout():
    response = make_response(jsonify({"message": "Logged out"}))
    response.delete_cookie("refreshToken", path="/")
    return response
