"""Miscellaneous endpoints the frontend expects to exist."""
import json
import uuid

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id, get_all_users, find_user_by_id, update_user_field

misc_bp = Blueprint("misc", __name__)

PROMPT_META_TYPE = "prompt"
FAVORITES_META_TYPE = "user_favorites"


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
    if usage["tokensRemaining"] <= 0:
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

@misc_bp.route("/api/mcp/tools", methods=["GET"])
@require_jwt
def mcp_tools():
    return jsonify([])


@misc_bp.route("/api/mcp/servers", methods=["GET"])
@require_jwt
def mcp_servers():
    return jsonify({})


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
    plan = get_user_plan(target)
    usage = get_token_usage(user_id)
    display_plan = "unlimited" if plan == "pro" else plan

    return jsonify({
        "plan": display_plan,
        "usageTokens": usage["usageTokens"],
        "includedTokens": usage["includedTokens"],
        "periodEnd": None,
        "stripeCustomerId": target.get("stripeCustomerId"),
        "stripeSubscriptionId": target.get("stripeSubscriptionId"),
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
    tokens = PLAN_TOKENS.get(plan, PLAN_TOKENS["free"])
    usage = get_token_usage(user_id)
    display_plan = "unlimited" if plan == "pro" else plan

    return jsonify({
        "plan": display_plan,
        "usageTokens": usage["usageTokens"],
        "includedTokens": tokens,
        "periodEnd": None,
        "stripeCustomerId": target.get("stripeCustomerId"),
        "stripeSubscriptionId": target.get("stripeSubscriptionId"),
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
    if request.method == "PUT":
        return jsonify(request.get_json() or {})
    return jsonify({})


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
