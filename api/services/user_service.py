"""User storage backed by Backboard memory on the auth assistant.

Recognizes both legacy LibreChat user records (type=librechat_user) and
Nash records (type=user). Preserves existing user IDs to avoid data loss.
The per-user Backboard assistant ID (bbAssistantId) is stored directly
on the user record, not in separate mapping entries.
"""
import json
import threading
import time
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from api.config import settings
from api.services.backboard_service import get_client
from api.services.async_runner import run_async

# Cache user records for up to 5 minutes.  update_user_field writes through
# and resets the timestamp, so in-app changes are never stale.
_USER_CACHE_TTL_SEC = 300
# (email -> (loaded_at_monotonic, user_dict))
_user_cache: dict[str, tuple[float, dict]] = {}

# Serialise Backboard user loads: only one thread fetches at a time.
# All concurrent callers wait on the lock then read from the populated cache.
_user_load_lock = threading.Lock()
_last_full_load: float = 0.0

USER_TYPES = {"user", "librechat_user"}


def _normalize_user(raw: dict) -> dict:
    """Normalize a user record from either format into a consistent shape."""
    return {
        "id": raw.get("_id") or raw.get("id") or "",
        "email": raw.get("email", ""),
        "name": raw.get("name", ""),
        "username": raw.get("username", raw.get("email", "").split("@")[0]),
        "avatar": raw.get("avatar", ""),
        "nickname": raw.get("nickname", ""),
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
        "stripeMeteredItemId": raw.get("stripeMeteredItemId", ""),
        "tokenUsage": raw.get("tokenUsage", 0),
        "tokenUsageResetAt": raw.get("tokenUsageResetAt", ""),
        "meteredOverageReportedUnits": raw.get("meteredOverageReportedUnits", 0),
        "referralCode": raw.get("referralCode", ""),
        "referredByCode": raw.get("referredByCode", ""),
        "referredByUserId": raw.get("referredByUserId", ""),
        "referredAt": raw.get("referredAt", ""),
        "referralRewardGrantedAt": raw.get("referralRewardGrantedAt", ""),
        "termsAcceptedAt": raw.get("termsAcceptedAt", ""),
        "twoFactorEnabled": raw.get("twoFactorEnabled", False),
        "totpSecret": raw.get("totpSecret", ""),
        "backupCodes": raw.get("backupCodes", []),
        "pendingTotpSecret": raw.get("pendingTotpSecret", ""),
        "pendingBackupCodes": raw.get("pendingBackupCodes", []),
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


def _is_cache_entry_fresh(entry: tuple[float, dict] | None) -> bool:
    return entry is not None and (time.monotonic() - entry[0]) < _USER_CACHE_TTL_SEC


def _cache_user(u: dict, loaded_at: float | None = None) -> None:
    """Cache a user, preferring librechat_user records over nash user records on collision."""
    email = u.get("email", "")
    if not email:
        return
    existing = _user_cache.get(email)
    if (
        existing
        and _is_cache_entry_fresh(existing)
        and existing[1].get("_raw_type") == "librechat_user"
        and u.get("_raw_type") != "librechat_user"
    ):
        return
    _user_cache[email] = (loaded_at if loaded_at is not None else time.monotonic(), u)


def _refresh_user_cache() -> None:
    """Load all users from Backboard with double-checked locking.

    Only one thread performs the Backboard fetch; concurrent callers wait on
    the lock and then read from the already-populated cache.  Without this,
    a cache expiry causes a stampede: N threads each submit
    _load_users_from_backboard() to the shared async event loop, the queue
    builds up, and the 30-second run_async timeout fires on every route.
    """
    global _last_full_load
    now = time.monotonic()
    if (now - _last_full_load) < _USER_CACHE_TTL_SEC:
        return
    with _user_load_lock:
        now = time.monotonic()
        if (now - _last_full_load) < _USER_CACHE_TTL_SEC:
            return
        users = run_async(_load_users_from_backboard())
        if users:
            loaded_at = time.monotonic()
            for u in users:
                _cache_user(u, loaded_at=loaded_at)
            _last_full_load = loaded_at


def find_user_by_email(email: str, *, force: bool = False) -> dict | None:
    """Look up a user by email.

    Pass force=True to bypass the TTL and unconditionally reload from
    Backboard.  Use this before creating a new user record to guarantee
    the user does not already exist, regardless of cache state.
    """
    if not force:
        entry = _user_cache.get(email)
        if _is_cache_entry_fresh(entry):
            return entry[1]
    with _user_load_lock:
        users = run_async(_load_users_from_backboard())
        if users:
            loaded_at = time.monotonic()
            for u in users:
                _cache_user(u, loaded_at=loaded_at)
            global _last_full_load
            _last_full_load = loaded_at
    entry = _user_cache.get(email)
    return entry[1] if entry else None


def find_user_by_id(user_id: str) -> dict | None:
    for entry in _user_cache.values():
        if _is_cache_entry_fresh(entry) and entry[1].get("id") == user_id:
            return entry[1]
    _refresh_user_cache()
    for entry in _user_cache.values():
        if entry[1].get("id") == user_id:
            return entry[1]
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
        _user_cache[email] = (time.monotonic(), user)


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
        "bbConfigAssistantId": "",
        "bbConfigMigrated": False,
        "plan": "free",
        "stripeCustomerId": "",
        "stripeSubscriptionId": "",
        "stripeMeteredItemId": "",
        "tokenUsage": 0,
        "tokenUsageResetAt": "",
        "meteredOverageReportedUnits": 0,
        "referralCode": "",
        "referredByCode": "",
        "referredByUserId": "",
        "referredAt": "",
        "referralRewardGrantedAt": "",
        "twoFactorEnabled": False,
        "totpSecret": "",
        "backupCodes": [],
        "pendingTotpSecret": "",
        "pendingBackupCodes": [],
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
        memory_id = result.get("id") or result.get("memory_id")
        if not memory_id:
            raise ValueError("Backboard add_memory response missing memory id")
        user_data["_memory_id"] = str(memory_id)
        return result

    run_async(_save())
    _user_cache[email] = (time.monotonic(), user_data)
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
    now = time.monotonic()
    for u in users:
        _cache_user(u, loaded_at=now)
    return [entry[1] for entry in _user_cache.values()]


def delete_user(user: dict) -> None:
    """Permanently delete a user's Backboard memory record and remove from cache.

    Does NOT delete the user's chat or config assistants — call the caller
    must wipe all memories from those assistants before calling this.
    """
    memory_id = user.get("_memory_id")
    if not memory_id:
        print(f"[delete_user] WARN: no _memory_id for user {user.get('email')} — auth record not deleted from Backboard")
    else:
        async def _delete():
            client = get_client()
            await client.delete_memory(
                assistant_id=settings.backboard_auth_assistant_id,
                memory_id=memory_id,
            )

        try:
            run_async(_delete())
        except Exception as e:
            print(f"[delete_user] ERROR deleting auth record for {user.get('email')}: {e}")

    email = user.get("email", "")
    if email:
        _user_cache.pop(email, None)  # type: ignore[arg-type]
