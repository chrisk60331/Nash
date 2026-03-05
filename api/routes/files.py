import json
import logging
import os
import uuid

from flask import Blueprint, request, jsonify, g, send_file

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id

files_bp = Blueprint("files", __name__)
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FILE_META_TYPE = "file_meta"


async def _list_file_metas(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    files = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != FILE_META_TYPE:
            continue
        try:
            f = json.loads(m.content)
            f["_memory_id"] = m.id
            files.append(f)
        except json.JSONDecodeError:
            continue
    return files


@files_bp.route("/api/files", methods=["GET"])
@require_jwt
def list_files():
    assistant_id = get_user_config_assistant_id(g.user_id)
    files = run_async(_list_file_metas(assistant_id))
    return jsonify([{k: v for k, v in f.items() if k != "_memory_id"} for f in files])


@files_bp.route("/api/files", methods=["POST"])
@require_jwt
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    # Client sends file_id in form (key used in UI file map); we generate server file_id for storage
    client_file_id = request.form.get("file_id")
    file_id = str(uuid.uuid4())
    filename = file.filename or "unknown"
    user_dir = os.path.join(UPLOAD_DIR, g.user_id)
    os.makedirs(user_dir, exist_ok=True)
    filepath = os.path.join(user_dir, f"{file_id}_{filename}")
    file.save(filepath)

    assistant_id = get_user_config_assistant_id(g.user_id)
    file_size = os.path.getsize(filepath)
    content_type = file.content_type or "application/octet-stream"

    file_meta = {
        "file_id": file_id,
        "filename": filename,
        "bytes": file_size,
        "type": content_type,
        "source": "local",
        "filepath": filepath,
    }

    async def _track_pending():
        client = get_client()
        pending_meta = {
            **file_meta,
            "status": "pending",
        }
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(pending_meta),
            metadata={"type": FILE_META_TYPE, "fileId": file_id, "filename": filename},
        )

    try:
        run_async(_track_pending())
        result = {
            **file_meta,
            "status": "pending",
        }
        # Client uses temp_file_id to update the file map entry (keyed by client's file_id)
        if client_file_id:
            result["temp_file_id"] = client_file_id
        return jsonify(result)
    except Exception as e:
        logger.exception("File upload tracking failed: %s", e)
        return jsonify({"error": str(e)}), 502


@files_bp.route("/api/files/download/<user_id>/<file_id>", methods=["GET"])
@require_jwt
def download_file(user_id, file_id):
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    if not os.path.isdir(user_dir):
        return jsonify({"error": "Not found"}), 404

    for fname in os.listdir(user_dir):
        if fname.startswith(file_id):
            return send_file(os.path.join(user_dir, fname))
    return jsonify({"error": "Not found"}), 404


@files_bp.route("/api/files", methods=["DELETE"])
@require_jwt
def delete_file():
    data = request.get_json(silent=True) or {}
    # Client sends { files: [ { file_id, ... } ] }; also support single file_id for backwards compat
    file_ids = []
    if "files" in data and isinstance(data["files"], list):
        for f in data["files"]:
            if isinstance(f, dict) and f.get("file_id"):
                file_ids.append(f["file_id"])
    single = data.get("file_id") or request.args.get("file_id")
    if single:
        file_ids.append(single)

    if not file_ids:
        return jsonify({"message": "Deleted"})

    assistant_id = get_user_config_assistant_id(g.user_id)
    files = run_async(_list_file_metas(assistant_id))

    for file_id in file_ids:
        for f in files:
            if f.get("file_id") == file_id:
                memory_id = f.get("_memory_id")
                if memory_id:
                    async def _del_mem(aid=assistant_id, mid=memory_id):
                        client = get_client()
                        await client.delete_memory(assistant_id=aid, memory_id=mid)

                    run_async(_del_mem())
                doc_id = f.get("document_id")
                if doc_id:
                    async def _del_doc(did=doc_id):
                        client = get_client()
                        try:
                            await client.delete_document(did)
                        except Exception as e:
                            logger.warning("Failed to delete Backboard document %s: %s", did, e)

                    run_async(_del_doc())
                local_path = f.get("filepath", "")
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)
                break

    return jsonify({"message": "Deleted"})


@files_bp.route("/api/files/config", methods=["GET"])
@require_jwt
def file_config():
    return jsonify({
        "endpoints": {},
        "serverFileSizeLimit": 50 * 1024 * 1024,
        "avatarSizeLimit": 2 * 1024 * 1024,
    })


@files_bp.route("/api/files/images/avatar", methods=["POST"])
@require_jwt
def upload_avatar():
    return jsonify({"url": ""})


@files_bp.route("/api/files/images/<path:subpath>", methods=["GET"])
def serve_image(subpath):
    return jsonify({"error": "Not found"}), 404
