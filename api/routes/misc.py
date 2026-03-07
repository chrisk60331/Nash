"""Miscellaneous endpoints the frontend expects to exist."""
import json
import re
import uuid

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import (
    get_user_config_assistant_id,
    get_user_assistant_id,
    get_all_users,
    find_user_by_id,
    update_user_field,
)
from api.services.mcp_service import fetch_mcp_tools, mcp_tools_to_openai_format, strip_server_prefix

misc_bp = Blueprint("misc", __name__)

PROMPT_META_TYPE = "prompt"
FAVORITES_META_TYPE = "user_favorites"
MCP_SERVER_META_TYPE = "mcp_server"


@misc_bp.route("/api/user/plugins", methods=["GET"])
@require_jwt
def user_plugins():
    return jsonify([])


@misc_bp.route("/api/user/plugins", methods=["POST"])
@require_jwt
def update_plugins():
    return jsonify([])


@misc_bp.route("/api/keys", methods=["GET"])
@require_jwt
def get_keys():
    return jsonify([])


@misc_bp.route("/api/banner", methods=["GET"])
def get_banner():
    from api.middleware.jwt_auth import decode_access_token
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if not token:
        return jsonify(None)

    try:
        payload = decode_access_token(token)
    except Exception:
        return jsonify(None)

    user_id = payload.get("sub", "")
    if not user_id:
        return jsonify(None)

    from api.services.token_service import get_token_usage
    usage = get_token_usage(user_id)
    if usage["tokensRemaining"] <= 0 and not usage.get("overageEnabled"):
        return jsonify({
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
        })

    return jsonify(None)


_ALL_PERMISSIONS = {
    "PROMPTS": {"USE": True, "CREATE": True, "SHARE": True, "SHARE_PUBLIC": True},
    "BOOKMARKS": {"USE": True},
    "MEMORIES": {"USE": True, "CREATE": True, "UPDATE": True, "READ": True, "OPT_OUT": True},
    "AGENTS": {"USE": True, "CREATE": True, "SHARE": True, "SHARE_PUBLIC": True},
    "MULTI_CONVO": {"USE": True},
    "TEMPORARY_CHAT": {"USE": True},
    "RUN_CODE": {"USE": True},
    "WEB_SEARCH": {"USE": True},
    "PEOPLE_PICKER": {"VIEW_USERS": True, "VIEW_GROUPS": True, "VIEW_ROLES": True},
    "MARKETPLACE": {"USE": True},
    "FILE_SEARCH": {"USE": True},
    "FILE_CITATIONS": {"USE": True},
    "MCP_SERVERS": {"USE": True, "CREATE": True, "SHARE": True, "SHARE_PUBLIC": True},
    "REMOTE_AGENTS": {"USE": True, "CREATE": True, "SHARE": True, "SHARE_PUBLIC": True},
}


@misc_bp.route("/api/roles", methods=["GET"])
@require_jwt
def get_roles():
    return jsonify([])


@misc_bp.route("/api/roles/<role_name>", methods=["GET"])
@require_jwt
def get_role(role_name):
    return jsonify({
        "name": role_name.upper(),
        "permissions": _ALL_PERMISSIONS,
    })


# --------------- Prompts ---------------

PROMPT_GROUP_META_TYPE = "prompt_group"


async def _list_prompt_groups_raw(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    groups = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != PROMPT_GROUP_META_TYPE:
            continue
        try:
            g_data = json.loads(m.content)
            g_data["_memory_id"] = m.id
            groups.append(g_data)
        except json.JSONDecodeError:
            continue
    return groups


def _clean(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if not k.startswith("_memory")}


def _make_prompt_group(group_id: str, name: str, prompt_text: str, prompt_type: str = "text",
                       author: str = "", author_name: str = "", **extra) -> dict:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    group = {
        "_id": group_id,
        "name": name,
        "author": author,
        "authorName": author_name,
        "productionPrompt": {
            "_id": str(uuid.uuid4()),
            "groupId": group_id,
            "prompt": prompt_text,
            "type": prompt_type,
            "createdAt": now,
            "updatedAt": now,
        },
        "createdAt": now,
        "updatedAt": now,
        **extra,
    }
    return group


@misc_bp.route("/api/prompts", methods=["GET"])
@require_jwt
def list_prompts():
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))
    return jsonify([_clean(gr) for gr in groups])


@misc_bp.route("/api/prompts/groups", methods=["GET"])
@require_jwt
def list_prompt_groups():
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))
    cleaned = [_clean(gr) for gr in groups]

    category = request.args.get("category", "")
    if category:
        cleaned = [gr for gr in cleaned if gr.get("category", "") == category]

    page_size = int(request.args.get("pageSize", "25"))
    page_number = int(request.args.get("pageNumber", "1"))
    start = (page_number - 1) * page_size
    page = cleaned[start:start + page_size]
    total_pages = max(1, (len(cleaned) + page_size - 1) // page_size)

    return jsonify({
        "promptGroups": page,
        "pageNumber": str(page_number),
        "pageSize": page_size,
        "pages": total_pages,
        "has_more": start + page_size < len(cleaned),
        "after": None,
    })


@misc_bp.route("/api/prompts/groups/<group_id>", methods=["GET"])
@require_jwt
def get_prompt_group(group_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))
    for gr in groups:
        if gr.get("_id") == group_id:
            return jsonify(_clean(gr))
    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/prompts/groups/<group_id>", methods=["PATCH"])
@require_jwt
def update_prompt_group(group_id):
    data = request.get_json() or {}
    payload = data.get("payload", data)
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))

    for gr in groups:
        if gr.get("_id") == group_id:
            memory_id = gr.get("_memory_id")
            gr.update({k: v for k, v in payload.items() if not k.startswith("_memory")})

            async def _update():
                client = get_client()
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps(_clean(gr)),
                    metadata={"type": PROMPT_GROUP_META_TYPE, "groupId": group_id},
                )

            run_async(_update())
            return jsonify(_clean(gr))

    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/prompts/groups/<group_id>", methods=["DELETE"])
@require_jwt
def delete_prompt_group(group_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))
    for gr in groups:
        if gr.get("_id") == group_id:
            memory_id = gr.get("_memory_id")
            if memory_id:
                async def _del():
                    client = get_client()
                    await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)
                run_async(_del())
            return jsonify({"prompt": group_id, "promptGroup": {"message": "Deleted", "id": group_id}})
    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/prompts/groups/<group_id>/prompts", methods=["POST"])
@require_jwt
def add_prompt_to_group(group_id):
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))

    for gr in groups:
        if gr.get("_id") == group_id:
            prompt_data = data.get("prompt", {})
            prompt_id = str(uuid.uuid4())
            prompt_obj = {
                "_id": prompt_id,
                "groupId": group_id,
                "prompt": prompt_data.get("prompt", ""),
                "type": prompt_data.get("type", "text"),
            }
            return jsonify({"prompt": prompt_obj, "group": _clean(gr)})

    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/prompts/all", methods=["GET"])
@require_jwt
def all_prompts():
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))
    return jsonify([_clean(gr) for gr in groups])


@misc_bp.route("/api/prompts/random", methods=["GET"])
@require_jwt
def random_prompts():
    return jsonify({"prompts": []})


@misc_bp.route("/api/prompts", methods=["POST"])
@require_jwt
def create_prompt():
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)

    prompt_input = data.get("prompt", {})
    group_input = data.get("group", {})

    group_id = str(uuid.uuid4())
    prompt_id = str(uuid.uuid4())
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    user = find_user_by_id(g.user_id)

    prompt_obj = {
        "_id": prompt_id,
        "groupId": group_id,
        "prompt": prompt_input.get("prompt", ""),
        "type": prompt_input.get("type", "text"),
        "createdAt": now,
        "updatedAt": now,
    }

    group_obj = {
        "_id": group_id,
        "name": group_input.get("name", "Untitled"),
        "author": g.user_id,
        "authorName": (user or {}).get("name", ""),
        "oneliner": group_input.get("oneliner", ""),
        "command": group_input.get("command", ""),
        "category": group_input.get("category", ""),
        "productionPrompt": prompt_obj,
        "createdAt": now,
        "updatedAt": now,
    }

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(group_obj),
            metadata={"type": PROMPT_GROUP_META_TYPE, "groupId": group_id},
        )

    run_async(_save())
    return jsonify({"prompt": prompt_obj, "group": group_obj}), 201


@misc_bp.route("/api/prompts/<prompt_id>", methods=["PATCH"])
@require_jwt
def update_prompt(prompt_id):
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))

    for gr in groups:
        prod = gr.get("productionPrompt", {})
        if prod.get("_id") == prompt_id or gr.get("_id") == prompt_id:
            memory_id = gr.get("_memory_id")
            if "prompt" in data:
                prod["prompt"] = data["prompt"]
            if "type" in data:
                prod["type"] = data["type"]
            gr["productionPrompt"] = prod

            async def _update():
                client = get_client()
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps(_clean(gr)),
                    metadata={"type": PROMPT_GROUP_META_TYPE, "groupId": gr.get("_id", "")},
                )

            run_async(_update())
            return jsonify(_clean(gr))

    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/prompts/<prompt_id>", methods=["DELETE"])
@require_jwt
def delete_prompt(prompt_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    groups = run_async(_list_prompt_groups_raw(assistant_id))
    for gr in groups:
        prod = gr.get("productionPrompt", {})
        if prod.get("_id") == prompt_id or gr.get("_id") == prompt_id:
            memory_id = gr.get("_memory_id")
            group_id = gr.get("_id", "")
            if memory_id:
                async def _del():
                    client = get_client()
                    await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)
                run_async(_del())
            return jsonify({"prompt": prompt_id, "promptGroup": {"message": "Deleted", "id": group_id}})
    return jsonify({"error": "Not found"}), 404


# --------------- MCP ---------------

def _sync_mcp_tools_to_assistant(user_id: str, config_assistant_id: str) -> None:
    """Collect all saved MCP server openai_tools and push to user's Backboard assistant."""
    try:
        chat_assistant_id = get_user_assistant_id(user_id)
        servers = run_async(_list_mcp_servers(config_assistant_id))
        all_tools = []
        for s in servers:
            all_tools.extend(s.get("openai_tools", []))

        async def _update():
            client = get_client()
            await client.update_assistant(
                assistant_id=chat_assistant_id,
                tools=all_tools,
            )

        run_async(_update())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("[mcp] failed to sync tools to assistant: %s", e)


@misc_bp.route("/api/mcp/tools", methods=["GET"])
@require_jwt
def mcp_tools():
    return jsonify([])


def _slugify_server_name(title: str) -> str:
    """Convert a human-readable title to a slug suitable for use as a serverName."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "mcp-server"


async def _list_mcp_servers(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    servers = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != MCP_SERVER_META_TYPE:
            continue
        try:
            s = json.loads(m.content)
            s["_memory_id"] = m.id
            servers.append(s)
        except json.JSONDecodeError:
            continue
    return servers


def _mcp_response(server: dict) -> dict:
    """Format a stored MCP server record as MCPServerDBObjectResponse."""
    config = server.get("config", {})
    return {
        "serverName": server.get("serverName", ""),
        "dbId": server.get("dbId", ""),
        **config,
    }


@misc_bp.route("/api/mcp/servers", methods=["GET"])
@require_jwt
def mcp_servers():
    assistant_id = get_user_config_assistant_id(g.user_id)
    servers = run_async(_list_mcp_servers(assistant_id))
    result = {}
    for s in servers:
        server_name = s.get("serverName", "")
        if server_name:
            result[server_name] = _mcp_response(s)
    return jsonify(result)


@misc_bp.route("/api/mcp/servers", methods=["POST"])
@require_jwt
def create_mcp_server():
    data = request.get_json() or {}
    config = data.get("config", {})
    title = (config.get("title") or "").strip()
    if not title:
        return jsonify({"error": "name is required"}), 400

    server_name = _slugify_server_name(title)
    assistant_id = get_user_config_assistant_id(g.user_id)
    servers = run_async(_list_mcp_servers(assistant_id))
    for s in servers:
        if s.get("serverName") == server_name:
            return jsonify({"error": "Server with this name already exists"}), 409

    db_id = str(uuid.uuid4())

    mcp_tools = run_async(fetch_mcp_tools({"config": config}))
    openai_tools = mcp_tools_to_openai_format(mcp_tools, server_name=server_name)

    server = {
        "serverName": server_name,
        "dbId": db_id,
        "config": config,
        "openai_tools": openai_tools,
    }

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(server),
            metadata={
                "type": MCP_SERVER_META_TYPE,
                "serverName": server_name,
                "dbId": db_id,
            },
        )

    run_async(_save())
    _sync_mcp_tools_to_assistant(g.user_id, assistant_id)
    return jsonify(_mcp_response(server)), 201


@misc_bp.route("/api/mcp/servers/<server_name>", methods=["GET"])
@require_jwt
def get_mcp_server(server_name: str):
    assistant_id = get_user_config_assistant_id(g.user_id)
    servers = run_async(_list_mcp_servers(assistant_id))
    for s in servers:
        if s.get("serverName") == server_name:
            return jsonify(_mcp_response(s))
    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/mcp/servers/<server_name>", methods=["PATCH"])
@require_jwt
def update_mcp_server(server_name: str):
    data = request.get_json() or {}
    config_update = data.get("config", {})

    assistant_id = get_user_config_assistant_id(g.user_id)
    servers = run_async(_list_mcp_servers(assistant_id))

    for s in servers:
        if s.get("serverName") == server_name:
            memory_id = s.get("_memory_id")
            s["config"] = {**s.get("config", {}), **config_update}

            async def _update():
                client = get_client()
                content = {k: v for k, v in s.items() if k != "_memory_id"}
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps(content),
                    metadata={
                        "type": MCP_SERVER_META_TYPE,
                        "serverName": server_name,
                        "dbId": s.get("dbId", ""),
                    },
                )

            run_async(_update())
            return jsonify(_mcp_response(s))

    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/mcp/servers/<server_name>", methods=["DELETE"])
@require_jwt
def delete_mcp_server(server_name: str):
    assistant_id = get_user_config_assistant_id(g.user_id)
    servers = run_async(_list_mcp_servers(assistant_id))

    for s in servers:
        if s.get("serverName") == server_name:
            memory_id = s.get("_memory_id")

            async def _delete():
                client = get_client()
                await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)

    run_async(_delete())
    _sync_mcp_tools_to_assistant(g.user_id, assistant_id)
    return jsonify({"success": True})

    return jsonify({"error": "Not found"}), 404


@misc_bp.route("/api/mcp/connection/status", methods=["GET"])
@require_jwt
def mcp_connection_status():
    return jsonify({})


# --------------- Admin ---------------

def _format_admin_user(u: dict) -> dict:
    return {
        "id": u.get("id", ""),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "username": u.get("username", ""),
        "avatar": u.get("avatar", ""),
        "role": u.get("role", "USER"),
        "provider": u.get("provider", ""),
        "createdAt": u.get("createdAt", ""),
    }


@misc_bp.route("/api/admin/users", methods=["GET"])
@require_jwt
def admin_users():
    user = find_user_by_id(g.user_id)
    print(f"[admin_users] caller={g.user_id}, user_found={user is not None}, role={user.get('role') if user else 'N/A'}")
    if not user or user.get("role", "").upper() != "ADMIN":
        return jsonify({"error": "Forbidden"}), 403

    q = request.args.get("q", "").lower().strip()
    try:
        users = get_all_users()
        print(f"[admin_users] loaded {len(users)} users from backboard")
    except Exception as e:
        print(f"[admin_users] ERROR loading users: {e}")
        return jsonify({"users": [], "total": 0})

    if q:
        users = [u for u in users if q in (u.get("name", "") + u.get("email", "")).lower()]

    formatted = [_format_admin_user(u) for u in users]
    return jsonify({"users": formatted, "total": len(formatted)})


@misc_bp.route("/api/admin/users/<user_id>/subscription", methods=["GET"])
@require_jwt
def get_admin_user_subscription(user_id):
    caller = find_user_by_id(g.user_id)
    if not caller or caller.get("role", "").upper() != "ADMIN":
        return jsonify({"error": "Forbidden"}), 403

    target = find_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    from api.routes.billing import get_user_plan
    from api.services.token_service import get_token_usage
    from api.services.balance_service import get_balance_response
    plan = get_user_plan(target)
    usage = get_token_usage(user_id)
    display_plan = "unlimited" if plan == "pro" else plan

    return jsonify({
        "plan": display_plan,
        "usageTokens": usage["usageTokens"],
        "includedTokens": usage["includedTokens"],
        "overageTokens": usage["overageTokens"],
        "periodEnd": None,
        "stripeCustomerId": target.get("stripeCustomerId"),
        "stripeSubscriptionId": target.get("stripeSubscriptionId"),
        "stripeMeteredItemId": target.get("stripeMeteredItemId"),
        "balance": get_balance_response(user_id),
        "referralCode": target.get("referralCode"),
        "referredByCode": target.get("referredByCode"),
        "referralRewardGrantedAt": target.get("referralRewardGrantedAt"),
    })


@misc_bp.route("/api/admin/users/<user_id>/subscription", methods=["PUT"])
@require_jwt
def update_admin_user_subscription(user_id):
    caller = find_user_by_id(g.user_id)
    if not caller or caller.get("role", "").upper() != "ADMIN":
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    plan = data.get("plan", "free")
    if plan == "unlimited":
        plan = "pro"
    if plan not in ("free", "plus", "pro"):
        plan = "free"

    target = find_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    update_user_field(target, "plan", plan)

    if "usageTokens" in data and data["usageTokens"] == 0:
        from api.services.token_service import reset_token_usage
        reset_token_usage(user_id)

    from api.routes.billing import PLAN_TOKENS
    from api.services.token_service import get_token_usage
    from api.services.balance_service import get_balance_response
    tokens = PLAN_TOKENS.get(plan, PLAN_TOKENS["free"])
    usage = get_token_usage(user_id)
    display_plan = "unlimited" if plan == "pro" else plan

    return jsonify({
        "plan": display_plan,
        "usageTokens": usage["usageTokens"],
        "includedTokens": tokens,
        "overageTokens": usage["overageTokens"],
        "periodEnd": None,
        "stripeCustomerId": target.get("stripeCustomerId"),
        "stripeSubscriptionId": target.get("stripeSubscriptionId"),
        "stripeMeteredItemId": target.get("stripeMeteredItemId"),
        "balance": get_balance_response(user_id),
        "referralCode": target.get("referralCode"),
        "referredByCode": target.get("referredByCode"),
        "referralRewardGrantedAt": target.get("referralRewardGrantedAt"),
    })


@misc_bp.route("/api/admin/users/set-role", methods=["PATCH"])
@require_jwt
def admin_set_role():
    caller = find_user_by_id(g.user_id)
    if not caller or caller.get("role", "").upper() != "ADMIN":
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    target_user_id = data.get("userId")
    new_role = data.get("role", "USER").upper()
    if not target_user_id:
        return jsonify({"error": "userId required"}), 400

    target = find_user_by_id(target_user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    update_user_field(target, "role", new_role)
    return jsonify({"userId": target_user_id, "role": new_role})


# --------------- Favorites ---------------

async def _get_favorites(assistant_id: str) -> dict:
    client = get_client()
    response = await client.get_memories(assistant_id)
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") == FAVORITES_META_TYPE:
            try:
                data = json.loads(m.content)
                data["_memory_id"] = m.id
                return data
            except json.JSONDecodeError:
                pass
    return {}


@misc_bp.route("/api/user/settings/favorites", methods=["GET"])
@require_jwt
def user_favorites():
    assistant_id = get_user_config_assistant_id(g.user_id)
    favs = run_async(_get_favorites(assistant_id))
    return jsonify({k: v for k, v in favs.items() if k != "_memory_id"})


@misc_bp.route("/api/user/settings/favorites", methods=["POST"])
@require_jwt
def update_favorites():
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    existing = run_async(_get_favorites(assistant_id))
    memory_id = existing.get("_memory_id")

    async def _save():
        client = get_client()
        if memory_id:
            await client.update_memory(
                assistant_id=assistant_id,
                memory_id=memory_id,
                content=json.dumps(data),
                metadata={"type": FAVORITES_META_TYPE},
            )
        else:
            await client.add_memory(
                assistant_id=assistant_id,
                content=json.dumps(data),
                metadata={"type": FAVORITES_META_TYPE},
            )

    run_async(_save())
    return jsonify(data)


# --------------- Speech / Permissions / Code Auth ---------------

@misc_bp.route("/api/files/speech/config/get", methods=["GET"])
@require_jwt
def speech_config():
    return jsonify({})


@misc_bp.route("/api/permissions/<resource_type>/effective/all", methods=["GET"])
@require_jwt
def all_effective_permissions(resource_type):
    return jsonify({})


@misc_bp.route("/api/permissions/<resource_type>/<resource_id>/effective", methods=["GET"])
@require_jwt
def resource_effective_permissions(resource_type, resource_id):
    return jsonify({
        "isOwner": True,
        "canRead": True,
        "canWrite": True,
        "canDelete": True,
        "canShare": True,
    })


@misc_bp.route("/api/permissions/<resource_type>/<resource_id>", methods=["GET", "PUT"])
@require_jwt
def resource_permissions(resource_type, resource_id):
    if resource_type.lower() != "agent":
        if request.method == "PUT":
            return jsonify(request.get_json() or {})
        return jsonify({"principals": [], "public": False})

    assistant_id = get_user_config_assistant_id(g.user_id)

    async def _find_agent():
        client = get_client()
        response = await client.get_memories(assistant_id)
        for m in response.memories:
            meta = m.metadata or {}
            if meta.get("type") != "agent":
                continue
            try:
                a = json.loads(m.content)
                if a.get("id") == resource_id or str(m.id) == resource_id:
                    return a, m.id
            except json.JSONDecodeError:
                continue
        return None, None

    agent_data, memory_id = run_async(_find_agent())

    if request.method == "GET":
        if not agent_data:
            return jsonify({"principals": [], "public": False})
        return jsonify({
            "principals": agent_data.get("_permissions", {}).get("principals", []),
            "public": agent_data.get("_permissions", {}).get("public", False),
            "publicAccessRoleId": agent_data.get("_permissions", {}).get("publicAccessRoleId"),
        })

    # PUT — persist the public flag and principals in the agent record
    data = request.get_json() or {}
    if not agent_data or not memory_id:
        return jsonify({"principals": [], "public": False})

    permissions = {
        "public": data.get("public", False),
        "publicAccessRoleId": data.get("publicAccessRoleId"),
        "principals": data.get("updated", []),
    }
    agent_data["_permissions"] = permissions
    agent_data["isPublic"] = data.get("public", False)

    async def _update_agent():
        client = get_client()
        content = {k: v for k, v in agent_data.items() if not k.startswith("_memory")}
        await client.update_memory(
            assistant_id=assistant_id,
            memory_id=memory_id,
            content=json.dumps(content),
            metadata={"type": "agent", "agentId": agent_data.get("id", "")},
        )

    run_async(_update_agent())
    return jsonify(permissions)


@misc_bp.route("/api/permissions/<resource_type>/roles", methods=["GET"])
@require_jwt
def permission_roles(resource_type):
    return jsonify([])


@misc_bp.route("/api/permissions/search-principals", methods=["GET"])
@require_jwt
def search_principals():
    return jsonify([])


@misc_bp.route("/api/agents/tools/execute_code/auth", methods=["GET"])
@require_jwt
def agent_tool_code_auth():
    return jsonify({"authenticated": False})
