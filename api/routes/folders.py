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


@folders_bp.route("/api/folders/<folder_id>", methods=["DELETE"])
@require_jwt
def delete_folder(folder_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    folders = run_async(_list_folders(assistant_id))
    for f in folders:
        if f.get("folderId") == folder_id:
            memory_id = f.get("_memory_id")
            if memory_id:
                async def _del():
                    client = get_client()
                    await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)
                run_async(_del())
            return jsonify({"message": "Deleted"})
    return jsonify({"error": "Not found"}), 404
