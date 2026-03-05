import json
import uuid

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id

presets_bp = Blueprint("presets", __name__)

PRESET_META_TYPE = "preset"


async def _list_presets(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    presets = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != PRESET_META_TYPE:
            continue
        try:
            p = json.loads(m.content)
            p["_memory_id"] = m.id
            presets.append(p)
        except json.JSONDecodeError:
            continue
    return presets


@presets_bp.route("/api/presets", methods=["GET"])
@require_jwt
def get_presets():
    assistant_id = get_user_config_assistant_id(g.user_id)
    presets = run_async(_list_presets(assistant_id))
    return jsonify(presets)


@presets_bp.route("/api/presets", methods=["POST"])
@require_jwt
def create_preset():
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    preset_id = data.get("presetId") or str(uuid.uuid4())
    data["presetId"] = preset_id

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(data),
            metadata={"type": PRESET_META_TYPE, "presetId": preset_id},
        )

    run_async(_save())
    return jsonify(data)


@presets_bp.route("/api/presets/delete", methods=["POST"])
@require_jwt
def delete_preset():
    data = request.get_json() or {}
    preset_id = data.get("presetId")
    if not preset_id:
        return jsonify({"error": "presetId required"}), 400

    assistant_id = get_user_config_assistant_id(g.user_id)
    presets = run_async(_list_presets(assistant_id))
    for p in presets:
        if p.get("presetId") == preset_id:
            memory_id = p.get("_memory_id")
            if memory_id:
                async def _del():
                    client = get_client()
                    await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)
                run_async(_del())
            return jsonify({"message": "Deleted"})
    return jsonify({"error": "Not found"}), 404
