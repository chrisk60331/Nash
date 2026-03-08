import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id

folders_bp = Blueprint("folders", __name__)

FOLDER_META_TYPE = "folder"


async def _list_folders(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    folders = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != FOLDER_META_TYPE:
            continue
        try:
            f = json.loads(m.content)
            f["_memory_id"] = m.id
            folders.append(f)
        except json.JSONDecodeError:
            continue
    return folders


@folders_bp.route("/api/folders", methods=["GET"])
@require_jwt
def get_folders():
    assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(assistant_id))
    return jsonify([{k: v for k, v in f.items() if k != "_memory_id"} for f in folders])


@folders_bp.route("/api/folders", methods=["POST"])
@require_jwt
def create_folder():
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    folder_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    folder = {
        "folderId": folder_id,
        "name": data.get("name", "New Folder"),
        "type": data.get("type", "conversation"),
        "createdAt": now,
        "updatedAt": now,
    }

    async def _save():
        client = get_client()
        bb_assistant = await client.create_assistant(
            name=f"nash-folder-{folder_id}",
            system_prompt="",
        )
        folder["bb_assistant_id"] = str(bb_assistant.assistant_id)
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(folder),
            metadata={"type": FOLDER_META_TYPE, "folderId": folder_id},
        )

    run_async(_save())
    return jsonify(folder)


@folders_bp.route("/api/folders/<folder_id>", methods=["PATCH"])
@require_jwt
def update_folder(folder_id):
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(assistant_id))

    for f in folders:
        if f.get("folderId") == folder_id:
            memory_id = f.get("_memory_id")
            if "name" in data:
                f["name"] = data["name"]
            f["updatedAt"] = datetime.now(timezone.utc).isoformat()

            async def _update():
                client = get_client()
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps({k: v for k, v in f.items() if k != "_memory_id"}),
                    metadata={"type": FOLDER_META_TYPE, "folderId": folder_id},
                )
            run_async(_update())
            return jsonify({k: v for k, v in f.items() if k != "_memory_id"})

    return jsonify({"error": "Not found"}), 404


@folders_bp.route("/api/folders/<folder_id>/memories", methods=["GET"])
@require_jwt
def list_folder_memories(folder_id):
    config_assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(config_assistant_id))

    target_assistant_id = None
    for f in folders:
        if f.get("folderId") == folder_id:
            target_assistant_id = f.get("bb_assistant_id")
            break

    if not target_assistant_id:
        return jsonify({"error": "Folder not found or has no isolated assistant"}), 404

    INTERNAL_TYPES = {"thread_mapping", "conversation_meta"}

    async def _fetch():
        client = get_client()
        response = await client.get_memories(target_assistant_id)
        memories = []
        for m in response.memories:
            meta = m.metadata or {}
            if meta.get("type", "") in INTERNAL_TYPES:
                continue
            content = m.content or ""
            memories.append({
                "key": str(m.id),
                "value": content,
                "updated_at": str(getattr(m, "updated_at", None) or getattr(m, "created_at", None) or ""),
                "tokenCount": len(content.split()),
            })
        return memories

    memories = run_async(_fetch())
    return jsonify({"memories": memories})


@folders_bp.route("/api/folders/<folder_id>/memories/<memory_id>", methods=["DELETE"])
@require_jwt
def delete_folder_memory(folder_id, memory_id):
    config_assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(config_assistant_id))

    target_assistant_id = None
    for f in folders:
        if f.get("folderId") == folder_id:
            target_assistant_id = f.get("bb_assistant_id")
            break

    if not target_assistant_id:
        return jsonify({"error": "Folder not found or has no isolated assistant"}), 404

    async def _del():
        client = get_client()
        await client.delete_memory(assistant_id=target_assistant_id, memory_id=memory_id)

    try:
        run_async(_del())
    except Exception:
        pass
    return jsonify({"message": "Deleted"})


@folders_bp.route("/api/folders/<folder_id>/memories", methods=["POST"])
@require_jwt
def create_folder_memory(folder_id):
    data = request.get_json() or {}
    config_assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(config_assistant_id))

    target_assistant_id = None
    for f in folders:
        if f.get("folderId") == folder_id:
            target_assistant_id = f.get("bb_assistant_id")
            break

    if not target_assistant_id:
        return jsonify({"error": "Folder not found or has no isolated assistant"}), 404

    key = data.get("key", "")
    value = data.get("value", "")
    if not value:
        return jsonify({"error": "value is required"}), 400

    content = f"{key}: {value}" if key else value

    async def _save():
        client = get_client()
        return await client.add_memory(
            assistant_id=target_assistant_id,
            content=content,
        )

    result = run_async(_save())
    memory_id = ""
    if isinstance(result, dict):
        memory_id = str(result.get("id") or result.get("memory_id", ""))
    else:
        memory_id = str(getattr(result, "id", "") or getattr(result, "memory_id", ""))

    return jsonify({
        "created": True,
        "memory": {"key": memory_id, "value": value},
    }), 201


@folders_bp.route("/api/folders/<folder_id>", methods=["DELETE"])
@require_jwt
def delete_folder(folder_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(assistant_id))
    for f in folders:
        if f.get("folderId") == folder_id:
            memory_id = f.get("_memory_id")
            bb_assistant_id = f.get("bb_assistant_id", "")

            async def _del(mid=memory_id, bbaid=bb_assistant_id):
                client = get_client()
                if bbaid:
                    try:
                        await client.delete_assistant(bbaid)
                    except Exception:
                        pass
                if mid:
                    await client.delete_memory(assistant_id=assistant_id, memory_id=mid)

            run_async(_del())
            return jsonify({"message": "Deleted"})
    return jsonify({"error": "Not found"}), 404
