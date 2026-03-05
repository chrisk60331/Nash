"""User storage backed by Backboard memory on the auth assistant.

Recognizes both legacy LibreChat user records (type=librechat_user) and
Nash records (type=user). Preserves existing user IDs to avoid data loss.
The per-user Backboard assistant ID (bbAssistantId) is stored directly
on the user record, not in separate mapping entries.
"""
import json
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from api.config import settings
from api.services.backboard_service import get_client
from api.services.async_runner import run_async

_user_cache: dict[str, dict] = {}

USER_TYPES = {"user", "librechat_user"}


def _normalize_user(raw: dict) -> dict:
    """Normalize a user record from either format into a consistent shape."""
    return {
        "id": raw.get("_id") or raw.get("id") or "",
        "email": raw.get("email", ""),
        "name": raw.get("name", ""),
        "username": raw.get("username", raw.get("email", "").split("@")[0]),
        "avatar": raw.get("avatar", ""),
        "provider": raw.get("provider", ""),
        "role": raw.get("role", "USER"),
        "googleId": raw.get("googleId", ""),
        "bbAssistantId": raw.get("bbAssistantId", ""),
        "bbConfigAssistantId": raw.get("bbConfigAssistantId", ""),
        "password_hash": raw.get("password_hash", ""),
        "bbConfigMigrated": raw.get("bbConfigMigrated", False),
        "plan": raw.get("plan", ""),
        "stripeCustomerId": raw.get("stripeCustomerId", ""),
        "stripeSubscriptionId": raw.get("stripeSubscriptionId", ""),
        "tokenUsage": raw.get("tokenUsage", 0),
        "tokenUsageResetAt": raw.get("tokenUsageResetAt", ""),
        "createdAt": raw.get("createdAt", ""),
        "updatedAt": raw.get("updatedAt", ""),
        "_memory_id": raw.get("_memory_id", ""),
        "_raw_type": raw.get("_raw_type", "user"),
    }


async def _load_users_from_backboard() -> list[dict]:
    client = get_client()
    response = await client.get_memories(settings.backboard_auth_assistant_id)
    users = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") not in USER_TYPES:
            continue
        try:
            user_data = json.loads(m.content)
        except json.JSONDecodeError:
            continue
        if not user_data.get("email"):
            continue
        user_data["_memory_id"] = m.id
        user_data["_raw_type"] = meta.get("type")
        users.append(_normalize_user(user_data))
    return users


def _cache_user(u: dict) -> None:
    """Cache a user, preferring librechat_user records over nash user records on collision."""
    email = u.get("email", "")
    if not email:
        return
    existing = _user_cache.get(email)
    if existing and existing.get("_raw_type") == "librechat_user" and u.get("_raw_type") != "librechat_user":
        return
    _user_cache[email] = u


def find_user_by_email(email: str) -> dict | None:
    if email in _user_cache:
        return _user_cache[email]
    users = run_async(_load_users_from_backboard())
    for u in users:
        _cache_user(u)
    return _user_cache.get(email)


def find_user_by_id(user_id: str) -> dict | None:
    for u in _user_cache.values():
        if u.get("id") == user_id:
            return u
    users = run_async(_load_users_from_backboard())
    for u in users:
        _cache_user(u)
        if u.get("id") == user_id:
            return u
    return None


def update_user_field(user: dict, field: str, value) -> None:
    """Update a single field on the user's Backboard memory record."""
    memory_id = user.get("_memory_id")
    if not memory_id:
        print(f"[update_user_field] WARN: no _memory_id for user {user.get('email')}, field={field} NOT persisted")
        return
    user[field] = value
    user["updatedAt"] = datetime.now(timezone.utc).isoformat()

    raw_type = user.get("_raw_type", "user")
    meta = {"type": raw_type, "email": user["email"]}
    if raw_type == "librechat_user":
        meta["entryId"] = user["id"]
        meta["updatedAt"] = user["updatedAt"]

    content = {k: v for k, v in user.items() if not k.startswith("_")}

    async def _update():
        client = get_client()
        await client.update_memory(
            assistant_id=settings.backboard_auth_assistant_id,
            memory_id=memory_id,
            content=json.dumps(content),
            metadata=meta,
        )

    try:
        run_async(_update())
    except Exception as e:
        print(f"[update_user_field] ERROR persisting {field}={value} for {user.get('email')}: {e}")
        return
    email = user.get("email", "")
    if email:
        _user_cache[email] = user


def create_user(
    email: str,
    name: str,
    avatar: str = "",
    provider: str = "google",
    role: str = "USER",
    username: str = "",
    password: str = "",
) -> dict:
    existing = find_user_by_email(email)
    if existing:
        return existing

    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "id": email.lower().strip(),
        "email": email,
        "name": name,
        "username": username or email.split("@")[0],
        "avatar": avatar,
        "provider": provider,
        "role": role,
        "password_hash": generate_password_hash(password) if password else "",
        "bbAssistantId": "",
        "createdAt": now,
        "updatedAt": now,
        "_raw_type": "user",
    }

    async def _save():
        client = get_client()
        result = await client.add_memory(
            assistant_id=settings.backboard_auth_assistant_id,
            content=json.dumps({k: v for k, v in user_data.items() if not k.startswith("_")}),
            metadata={"type": "user", "email": email, "user_id": user_data["id"]},
        )
        user_data["_memory_id"] = result.id
        return result

    run_async(_save())
    _user_cache[email] = user_data
    return user_data


def verify_password(user: dict, password: str) -> bool:
    pw_hash = user.get("password_hash", "")
    if not pw_hash:
        return False
    return check_password_hash(pw_hash, password)


def get_user_assistant_id(user_id: str) -> str:
    """Get the bbAssistantId for a user. Assumes login already ensured it exists."""
    user = find_user_by_id(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    assistant_id = user.get("bbAssistantId", "")
    if not assistant_id:
        raise ValueError(f"User {user_id} has no bbAssistantId — re-login required")
    return assistant_id


def get_user_config_assistant_id(user_id: str) -> str:
    """Get the bbConfigAssistantId for a user, falling back to bbAssistantId for legacy users."""
    user = find_user_by_id(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    config_id = user.get("bbConfigAssistantId", "")
    if config_id:
        return config_id
    assistant_id = user.get("bbAssistantId", "")
    if not assistant_id:
        raise ValueError(f"User {user_id} has no bbAssistantId — re-login required")
    return assistant_id


def get_all_users() -> list[dict]:
    users = run_async(_load_users_from_backboard())
    for u in users:
        _cache_user(u)
    return list(_user_cache.values())
