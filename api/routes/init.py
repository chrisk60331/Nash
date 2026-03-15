"""Batch init endpoint — replaces ~15 individual API calls on page load.

Fetches the user's config-assistant memories ONCE and partitions them by
metadata type, then combines with cheap/static data so the frontend can
hydrate everything from a single request.
"""
import json
import logging
import threading
import time
from concurrent.futures import TimeoutError

from flask import Blueprint, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import (
    find_user_by_id,
    get_user_config_assistant_id,
)
from api.routes.config_routes import _build_endpoints_response, _build_models_response
from api.services.balance_service import get_balance_response_from_memories

logger = logging.getLogger(__name__)

init_bp = Blueprint("init", __name__)

INIT_CACHE_TTL_SEC = 10
INIT_BACKBOARD_TIMEOUT_SEC = 12
_init_cache: dict[str, tuple[float, dict]] = {}
_init_cache_lock = threading.Lock()

CONVO_META_TYPE = "conversation_meta"
THREAD_MAP_TYPE = "thread_mapping"
AGENT_META_TYPE = "agent"
FILE_META_TYPE = "file_meta"
PRESET_META_TYPE = "preset"
PROMPT_GROUP_META_TYPE = "prompt_group"
FAVORITES_META_TYPE = "user_favorites"
TAG_META_TYPE = "tag"
FOLDER_META_TYPE = "folder"
MCP_SERVER_META_TYPE = "mcp_server"


def _parse_memory(m) -> tuple[str, dict | None]:
    """Return (type, parsed_content) or (type, None) on decode error."""
    meta = m.metadata or {}
    mtype = meta.get("type", "")
    try:
        data = json.loads(m.content)
        data["_memory_id"] = m.id
        data["_meta"] = meta
        return mtype, data
    except (json.JSONDecodeError, TypeError):
        return mtype, None


def _clean(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if not k.startswith("_")}


def _migrate_agents_background(agents: list[dict], config_assistant_id: str) -> None:
    """Run agent bb_assistant_id migration in a background thread."""
    needs_migration = [a for a in agents if not a.get("bb_assistant_id")]
    if not needs_migration:
        return

    def _do_migration():
        try:
            for a in needs_migration:
                memory_id = a.get("_memory_id")
                if not memory_id:
                    continue
                try:
                    bb = run_async(get_client().create_assistant(
                        name=f"nash-agent-{a['id']}",
                        system_prompt=a.get("instructions", ""),
                    ))
                    a["bb_assistant_id"] = str(bb.assistant_id)
                    logger.info("[agents] bg-migration: created Backboard assistant %s for agent %s",
                                a["bb_assistant_id"], a["id"])
                    content = {k: v for k, v in a.items() if not k.startswith("_")}
                    run_async(get_client().update_memory(
                        assistant_id=config_assistant_id,
                        memory_id=memory_id,
                        content=json.dumps(content),
                        metadata={"type": AGENT_META_TYPE, "agentId": content["id"]},
                    ))
                except Exception:
                    logger.exception("[agents] bg-migration: failed for agent %s", a.get("id"))
        except Exception:
            logger.exception("[agents] bg-migration: unexpected error")

    threading.Thread(target=_do_migration, daemon=True).start()


@init_bp.route("/api/init", methods=["GET"])
@require_jwt
def init():
    now = time.monotonic()
    with _init_cache_lock:
        cached = _init_cache.get(g.user_id)
        if cached and (now - cached[0]) < INIT_CACHE_TTL_SEC:
            return jsonify(cached[1])

    try:
        config_assistant_id = get_user_config_assistant_id(g.user_id)
    except ValueError:
        resp = jsonify({"error": "user_not_found"})
        resp.headers["Retry-After"] = "5"
        return resp, 503

    try:
        response = run_async(
            get_client().get_memories(config_assistant_id),
            timeout=INIT_BACKBOARD_TIMEOUT_SEC,
        )
    except TimeoutError:
        return jsonify({"error": "Backboard timeout"}), 503

    agents = []
    files = []
    presets = []
    convos = []
    prompt_groups = []
    favorites = {}
    tags = []
    folders = []
    mcp_servers = []

    for m in response.memories:
        mtype, data = _parse_memory(m)
        if data is None:
            continue

        if mtype == AGENT_META_TYPE:
            old_id = data.get("id", "")
            if old_id and not old_id.startswith("agent_"):
                data["id"] = f"agent_{old_id}"
            agents.append(data)

        elif mtype == FILE_META_TYPE:
            files.append(data)

        elif mtype == PRESET_META_TYPE:
            presets.append(data)

        elif mtype == CONVO_META_TYPE:
            meta = data.get("_meta", {})
            data["conversationId"] = meta.get("conversationId", "")
            data["createdAt"] = meta.get("createdAt", "")
            data["updatedAt"] = meta.get("updatedAt", "")
            convos.append(data)

        elif mtype == PROMPT_GROUP_META_TYPE:
            prompt_groups.append(data)

        elif mtype == FAVORITES_META_TYPE:
            favorites = data

        elif mtype == TAG_META_TYPE:
            tags.append(data)

        elif mtype == FOLDER_META_TYPE:
            folders.append(data)

        elif mtype == MCP_SERVER_META_TYPE:
            mcp_servers.append(data)

    _migrate_agents_background(agents, config_assistant_id)

    convos.sort(key=lambda c: c.get("updatedAt", ""), reverse=True)

    user = find_user_by_id(g.user_id)
    from api.routes.billing import get_user_plan, PLAN_TOKENS
    from api.services.token_service import get_token_usage
    plan = get_user_plan(user)
    usage = get_token_usage(g.user_id)
    display_plan = "unlimited" if plan == "pro" else plan

    cleaned_agents = [_clean(a) for a in agents]
    page_size = 25
    convo_page = [_format_convo(c) for c in convos[:page_size]]

    payload = {
        "agents": {
            "object": "list",
            "data": cleaned_agents,
            "first_id": cleaned_agents[0]["id"] if cleaned_agents else "",
            "last_id": cleaned_agents[-1]["id"] if cleaned_agents else "",
            "has_more": False,
        },
        "files": [_clean(f) for f in files],
        "presets": [_clean(p) for p in presets],
        "conversations": {
            "conversations": convo_page,
            "pageSize": page_size,
            "pages": 1,
            "pageNumber": "1",
            "nextCursor": convo_page[-1]["conversationId"] if len(convo_page) == page_size else None,
        },
        "promptGroups": [_clean(pg) for pg in prompt_groups],
        "allPrompts": [_clean(pg) for pg in prompt_groups],
        "favorites": _clean(favorites) if favorites else {},
        "tags": [_clean(t) for t in tags],
        "folders": [_clean(f) for f in folders],
        "balance": get_balance_response_from_memories(response.memories, g.user_id),
        "subscription": {
            "subscription": display_plan if plan != "free" else None,
            "plan": display_plan,
            "status": "active",
            "usageTokens": usage["usageTokens"],
            "tokensRemaining": usage["tokensRemaining"],
            "includedTokens": usage["includedTokens"],
        },
        "models": _build_models_response(),
        "endpoints": _build_endpoints_response(),
        "startupConfig": _get_startup_config(),
        "searchEnabled": {"enabled": True},
        "keys": [],
        "mcpServers": {
            s.get("serverName"): {
                k: v for k, v in s.items()
                if k not in ("_memory_id", "_meta", "openai_tools")
            }
            for s in mcp_servers
            if s.get("serverName")
        },
        "mcpTools": [],
        "agentTools": [],
        "agentCategories": [],
        "activeJobs": [],
        "codeAuth": {"authenticated": False},
        "permissions": {},
        "fileConfig": _file_config_data(),
        "banner": _get_banner_data(usage),
    }

    with _init_cache_lock:
        _init_cache[g.user_id] = (now, payload)

    return jsonify(payload)


def _format_convo(c: dict) -> dict:
    return {
        "conversationId": c.get("conversationId", ""),
        "title": c.get("title", "New Chat"),
        "endpoint": c.get("endpoint", "custom"),
        "model": c.get("model", ""),
        "chatGptLabel": c.get("chatGptLabel"),
        "modelLabel": c.get("modelLabel"),
        "user": c.get("user"),
        "createdAt": c.get("createdAt", ""),
        "updatedAt": c.get("updatedAt", ""),
        "isArchived": c.get("isArchived", False),
        "tags": c.get("tags", []),
        "folderId": c.get("folderId"),
    }


def _get_startup_config() -> dict:
    from api.config import settings
    from api.routes.config_routes import FREE_TIER_PROVIDERS
    from api.services.org_security_service import get_org_security_config
    org_security_config = get_org_security_config()
    return {
        "appTitle": settings.app_title,
        "socialLogins": ["google"],
        "discordLoginEnabled": False,
        "facebookLoginEnabled": False,
        "githubLoginEnabled": False,
        "googleLoginEnabled": True,
        "openidLoginEnabled": False,
        "appleLoginEnabled": False,
        "samlLoginEnabled": False,
        "openidLabel": "",
        "openidImageUrl": "",
        "openidAutoRedirect": False,
        "samlLabel": "",
        "samlImageUrl": "",
        "serverDomain": settings.domain_server,
        "emailLoginEnabled": settings.allow_email_login,
        "registrationEnabled": settings.allow_registration,
        "socialLoginEnabled": settings.allow_social_login,
        "passwordResetEnabled": False,
        "emailEnabled": False,
        "showBirthdayIcon": False,
        "helpAndFaqURL": settings.help_and_faq_url,
        "requireMfaForAllUsers": org_security_config.requireMfaForAllUsers,
        "sharedLinksEnabled": settings.allow_shared_links,
        "publicSharedLinksEnabled": settings.allow_shared_links,
        "instanceProjectId": "nash-2",
        "interface": {
            "webSearch": True,
            "endpointsMenu": True,
            "modelSelect": True,
            "parameters": True,
            "sidePanel": True,
            "presets": True,
            "bookmarks": True,
            "agents": {"use": True, "create": True, "share": False, "public": False},
            "prompts": True,
            "multiConvo": False,
            "artifacts": False,
            "codeBrowser": False,
            "fileCitations": True,
            "remoteAgents": {"use": False, "create": False, "share": False, "public": False},
        },
        "billing": {
            "enabled": True,
            "freeModels": [p.lower() for p in FREE_TIER_PROVIDERS],
            "priceIdPlus": settings.stripe_price_id_plus,
            "priceIdUnlimited": settings.stripe_price_id_unlimited,
            "plans": {
                "free": {
                    "tokens": settings.free_included_tokens,
                    "label": "Free",
                    "overageEnabled": False,
                },
                "plus": {
                    "tokens": settings.plus_included_tokens,
                    "label": "Plus",
                    "priceId": settings.stripe_price_id_plus,
                    "overageEnabled": bool(settings.stripe_metered_price_id_plus),
                    "overagePriceId": settings.stripe_metered_price_id_plus,
                    "overageTokensPerUnit": settings.stripe_overage_tokens_per_unit,
                    "overageUnitPriceUsd": settings.stripe_overage_unit_price_usd,
                },
                "pro": {
                    "tokens": settings.pro_included_tokens,
                    "label": "Pro",
                    "priceId": settings.stripe_price_id_unlimited,
                    "overageEnabled": bool(settings.stripe_metered_price_id_unlimited),
                    "overagePriceId": settings.stripe_metered_price_id_unlimited,
                    "overageTokensPerUnit": settings.stripe_overage_tokens_per_unit,
                    "overageUnitPriceUsd": settings.stripe_overage_unit_price_usd,
                },
            },
        },
        "balance": {
            "enabled": True,
            "tokenCreditsPerUsd": settings.token_credits_per_usd,
        },
        "referrals": {
            "enabled": True,
            "rewardUsd": settings.referral_bonus_usd,
        },
    }


def _file_config_data() -> dict:
    return {
        "endpoints": {
            "default": {
                "fileLimit": 10,
                "fileSizeLimit": 25 * 1024 * 1024,
                "supportedMimeTypes": ["*/*"],
                "disabled": False,
            }
        },
        "serverFileSizeLimit": 100 * 1024 * 1024,
        "avatarSizeLimit": 2 * 1024 * 1024,
    }


def _get_banner_data(usage: dict):
    if usage["tokensRemaining"] <= 0 and not usage.get("overageEnabled"):
        return {
            "bannerId": "token-limit-reached",
            "message": (
                "\u26a0\ufe0f You\u2019ve used all your tokens this month. "
                "Open <b>Settings \u2192 Billing</b> from the bottom-left menu to upgrade."
            ),
            "displayFrom": "2020-01-01T00:00:00Z",
            "displayTo": "2099-12-31T23:59:59Z",
            "createdAt": "2020-01-01T00:00:00Z",
            "updatedAt": "2020-01-01T00:00:00Z",
            "isPublic": False,
            "persistable": True,
        }
    return None
