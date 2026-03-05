from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_assistant_id

memories_bp = Blueprint("memories", __name__)

INTERNAL_TYPES = {
    "thread_mapping", "conversation_meta",
    "prompt", "prompt_group", "user_favorites",
    "file_meta", "agent", "shared_link",
    "tag", "folder", "preset",
    "user", "librechat_user", "user_memory",
}


@memories_bp.route("/api/memories", methods=["GET"])
@require_jwt
def list_memories():
    assistant_id = get_user_assistant_id(g.user_id)

    async def _fetch():
        client = get_client()
        response = await client.get_memories(assistant_id)
        memories = []
        for m in response.memories:
            meta = m.metadata or {}
            mem_type = meta.get("type", "")
            if mem_type in INTERNAL_TYPES:
                continue
            memories.append({
                "key": str(m.id),
                "value": m.content or "",
                "updated_at": getattr(m, "updated_at", None)
                    or getattr(m, "created_at", None)
                    or "",
                "tokenCount": len((m.content or "").split()),
            })
        return memories

    mems = run_async(_fetch())
    total_tokens = sum(m.get("tokenCount", 0) for m in mems)
    return jsonify({
        "memories": mems,
        "totalTokens": total_tokens,
        "tokenLimit": None,
        "usagePercentage": None,
    })


@memories_bp.route("/api/memories", methods=["POST"])
@require_jwt
def create_memory():
    data = request.get_json() or {}
    assistant_id = get_user_assistant_id(g.user_id)
    value = data.get("value", "")

    async def _save():
        client = get_client()
        result = await client.add_memory(
            assistant_id=assistant_id,
            content=value,
        )
        return result

    result = run_async(_save())
    return jsonify({
        "key": str(result.id),
        "value": value,
        "updated_at": getattr(result, "updated_at", None)
            or getattr(result, "created_at", None)
            or "",
        "tokenCount": len(value.split()),
    })


@memories_bp.route("/api/memories/<key>", methods=["PATCH"])
@require_jwt
def update_memory(key):
    data = request.get_json() or {}
    assistant_id = get_user_assistant_id(g.user_id)
    new_value = data.get("value", "")

    async def _update():
        client = get_client()
        await client.update_memory(
            assistant_id=assistant_id,
            memory_id=key,
            content=new_value,
        )

    try:
        run_async(_update())
    except Exception:
        pass
    return jsonify({
        "key": key,
        "value": new_value,
        "updated_at": "",
        "tokenCount": len(new_value.split()),
    })


@memories_bp.route("/api/memories/<key>", methods=["DELETE"])
@require_jwt
def delete_memory(key):
    assistant_id = get_user_assistant_id(g.user_id)

    async def _del():
        client = get_client()
        await client.delete_memory(assistant_id=assistant_id, memory_id=key)

    try:
        run_async(_del())
    except Exception:
        pass
    return jsonify({"message": "Deleted"})


@memories_bp.route("/api/memories/preferences", methods=["GET"])
@require_jwt
def memory_preferences():
    return jsonify({"enabled": True})


@memories_bp.route("/api/memories/preferences", methods=["PATCH", "POST"])
@require_jwt
def update_memory_preferences():
    return jsonify({"enabled": True})
