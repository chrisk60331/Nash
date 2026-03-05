from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.user_service import get_user_assistant_id, get_user_config_assistant_id
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.conversation_service import (
    list_conversations,
    save_conversation_meta,
    delete_conversation_meta,
    get_thread_id_for_conversation,
)

conversations_bp = Blueprint("conversations", __name__)


@conversations_bp.route("/api/convos", methods=["GET"])
@require_jwt
def get_conversations():
    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)

    is_archived = request.args.get("isArchived", "false").lower() == "true"
    folder_id = request.args.get("folderId")
    tags = request.args.getlist("tags")

    filtered = []
    for c in convos:
        if c.get("isArchived", False) != is_archived:
            continue
        if folder_id and folder_id != "none" and c.get("folderId") != folder_id:
            continue
        if tags and not any(t in (c.get("tags") or []) for t in tags):
            continue
        filtered.append(c)

    page_size = int(request.args.get("pageSize", "25"))
    cursor = request.args.get("cursor")

    start_idx = 0
    if cursor:
        for i, c in enumerate(filtered):
            if c.get("conversationId") == cursor:
                start_idx = i + 1
                break

    page = filtered[start_idx:start_idx + page_size]
    next_cursor = page[-1]["conversationId"] if len(page) == page_size else None

    return jsonify({
        "conversations": [_format_convo(c) for c in page],
        "pageSize": page_size,
        "pages": 1,
        "pageNumber": "1",
        "nextCursor": next_cursor,
    })


@conversations_bp.route("/api/convos/<conversation_id>", methods=["GET"])
@require_jwt
def get_conversation(conversation_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)
    for c in convos:
        if c.get("conversationId") == conversation_id:
            return jsonify(_format_convo(c))
    return jsonify({"error": "Not found"}), 404


@conversations_bp.route("/api/convos/update", methods=["POST"])
@require_jwt
def update_conversation():
    data = request.get_json() or {}
    arg = data.get("arg", {})
    conversation_id = arg.get("conversationId")
    if not conversation_id:
        return jsonify({"error": "conversationId required"}), 400

    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)
    existing = None
    for c in convos:
        if c.get("conversationId") == conversation_id:
            existing = c
            break

    meta = existing or {"conversationId": conversation_id}
    if "title" in arg:
        meta["title"] = arg["title"]
    if "folderId" in arg:
        meta["folderId"] = arg["folderId"]
    if "tags" in arg:
        meta["tags"] = arg["tags"]

    save_conversation_meta(assistant_id, conversation_id, meta)
    return jsonify(_format_convo(meta))


@conversations_bp.route("/api/convos/archive", methods=["POST"])
@require_jwt
def archive_conversation():
    data = request.get_json() or {}
    conversation_id = data.get("conversationId")
    is_archived = data.get("isArchived", True)
    if not conversation_id:
        return jsonify({"error": "conversationId required"}), 400

    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)
    for c in convos:
        if c.get("conversationId") == conversation_id:
            c["isArchived"] = is_archived
            save_conversation_meta(assistant_id, conversation_id, c)
            return jsonify(_format_convo(c))
    return jsonify({"error": "Not found"}), 404


@conversations_bp.route("/api/convos", methods=["DELETE"])
@require_jwt
def delete_conversation():
    data = request.get_json() or {}
    arg = data.get("arg", data)
    conversation_id = arg.get("conversationId") or data.get("conversationId")
    if not conversation_id:
        return jsonify({"error": "conversationId required"}), 400

    assistant_id = get_user_config_assistant_id(g.user_id)
    delete_conversation_meta(assistant_id, conversation_id)
    return jsonify({"message": "Deleted"})


@conversations_bp.route("/api/convos/gen_title/<conversation_id>", methods=["GET"])
@require_jwt
def gen_title(conversation_id):
    config_id = get_user_config_assistant_id(g.user_id)
    chat_id = get_user_assistant_id(g.user_id)
    thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=config_id)
    if not thread_id:
        return jsonify({"title": "New Chat"})

    async def _generate():
        client = get_client()
        thread = await client.get_thread(thread_id)
        if not thread.messages:
            return "New Chat"
        first_user = ""
        first_assistant = ""
        for m in thread.messages[:4]:
            if m.role == "user" and not first_user:
                first_user = (m.content or "")[:200]
            elif m.role == "assistant" and not first_assistant:
                first_assistant = (m.content or "")[:200]
        snippet = first_user or first_assistant or "New Chat"
        title_thread = await client.create_thread(chat_id)
        resp = await client.add_message(
            thread_id=title_thread.thread_id,
            content=f"Generate a concise title (max 6 words) for a conversation that starts with: \"{snippet}\". Reply with ONLY the title, no quotes.",
            stream=False,
        )
        return (resp.content or "New Chat").strip().strip('"').strip("'")[:80]

    try:
        title = run_async(_generate())
    except Exception:
        title = None

    if title and title != "New Chat":
        save_conversation_meta(config_id, conversation_id, {"title": title})
    elif not title:
        title = "New Chat"

    return jsonify({"title": title})


@conversations_bp.route("/api/convos/fork", methods=["POST"])
@require_jwt
def fork_conversation():
    return jsonify({"error": "Not implemented"}), 501


@conversations_bp.route("/api/convos/duplicate", methods=["POST"])
@require_jwt
def duplicate_conversation():
    return jsonify({"error": "Not implemented"}), 501


@conversations_bp.route("/api/convos/<conversation_id>/folder", methods=["PUT"])
@require_jwt
def move_to_folder(conversation_id):
    data = request.get_json() or {}
    folder_id = data.get("folderId")
    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)
    for c in convos:
        if c.get("conversationId") == conversation_id:
            c["folderId"] = folder_id
            save_conversation_meta(assistant_id, conversation_id, c)
            return jsonify(_format_convo(c))
    return jsonify({"error": "Not found"}), 404


def _normalize_endpoint(ep: str) -> str:
    if not ep or ep == "custom" or ep == "agents":
        return "AWS Bedrock"
    return ep


def _format_convo(c: dict) -> dict:
    result = {
        "conversationId": c.get("conversationId", ""),
        "title": c.get("title", "New Chat"),
        "endpoint": _normalize_endpoint(c.get("endpoint", "")),
        "model": c.get("model", ""),
        "isArchived": c.get("isArchived", False),
        "tags": c.get("tags", []),
        "createdAt": c.get("createdAt", ""),
        "updatedAt": c.get("updatedAt", ""),
    }
    if c.get("endpointType"):
        result["endpointType"] = c["endpointType"]
    if c.get("user"):
        result["user"] = c["user"]
    if c.get("modelLabel"):
        result["modelLabel"] = c["modelLabel"]
    if c.get("folderId"):
        result["folderId"] = c["folderId"]
    return result
