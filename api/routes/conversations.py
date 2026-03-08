import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.user_service import get_user_assistant_id, get_user_config_assistant_id
from api.services.backboard_service import get_client, get_thread_messages
from api.services.async_runner import run_async
from api.services.conversation_service import (
    list_conversations,
    save_conversation_meta,
    delete_conversation_meta,
    get_thread_id_for_conversation,
    get_or_create_thread,
    list_folder_conversation_ids,
    add_thread_mapping,
    remove_thread_mapping,
)

conversations_bp = Blueprint("conversations", __name__)


@conversations_bp.route("/api/convos", methods=["GET"])
@require_jwt
def get_conversations():
    assistant_id = get_user_assistant_id(g.user_id)
    config_assistant_id = get_user_config_assistant_id(g.user_id)

    is_archived = request.args.get("isArchived", "false").lower() == "true"
    folder_id = request.args.get("folderId")
    tags = request.args.getlist("tags")

    if folder_id and folder_id != "none":
        # Folder-native listing: enumerate thread_mappings on the folder's BB assistant.
        folder_bb_assistant_id = run_async(_get_bb_assistant_id_for_folder(config_assistant_id, folder_id))
        if not folder_bb_assistant_id:
            return jsonify({"conversations": [], "pageSize": 25, "pages": 1, "pageNumber": "1", "nextCursor": None})

        folder_entries = list_folder_conversation_ids(folder_bb_assistant_id)
        all_convos = list_conversations(assistant_id)
        meta_by_id = {c.get("conversationId"): c for c in all_convos}

        convos = []
        for entry in folder_entries:
            cid = entry["conversationId"]
            meta = meta_by_id.get(cid)
            if meta:
                if not meta.get("folderId"):
                    # Lazy migration: old conversation predates folderId tagging.
                    # Patch the meta in Backboard so future loads (including get_conversation)
                    # return the correct folderId, and the chat payload carries it.
                    patched = {**meta, "folderId": folder_id, "hidden": True}
                    save_conversation_meta(assistant_id, cid, {"folderId": folder_id, "hidden": True})
                    convos.append(patched)
                else:
                    convos.append(meta)
            else:
                convos.append({"conversationId": cid, "title": "New Chat", "endpoint": "", "model": "", "isArchived": False, "tags": [], "createdAt": "", "updatedAt": "", "folderId": folder_id, "hidden": True})

        filtered = [c for c in convos if c.get("isArchived", False) == is_archived]
        if tags:
            filtered = [c for c in filtered if any(t in (c.get("tags") or []) for t in tags)]
    else:
        # Main list: exclude conversations that belong to a folder.
        all_convos = list_conversations(assistant_id)
        filtered = []
        for c in all_convos:
            if c.get("isArchived", False) != is_archived:
                continue
            if c.get("hidden") or c.get("folderId"):
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
    assistant_id = get_user_assistant_id(g.user_id)
    config_assistant_id = get_user_config_assistant_id(g.user_id)

    convos = list_conversations(assistant_id)
    for c in convos:
        if c.get("conversationId") == conversation_id:
            return jsonify(_format_convo(c))

    # Not found in main assistant — conversation may only have a thread_mapping on a
    # folder's BB assistant (created before conversation_meta lazy-write was added).
    # Scan all folder assistants to find the owning folder.
    folder_id, folder_bb_aid = run_async(
        _find_folder_for_conversation(config_assistant_id, conversation_id)
    )
    if folder_id:
        now = datetime.now(timezone.utc).isoformat()
        synthetic = {
            "conversationId": conversation_id,
            "title": "New Chat",
            "endpoint": "",
            "model": "",
            "isArchived": False,
            "tags": [],
            "folderId": folder_id,
            "hidden": True,
            "createdAt": now,
            "updatedAt": now,
        }
        # Persist so subsequent loads (including chat routing) find it immediately.
        save_conversation_meta(assistant_id, conversation_id, synthetic)
        return jsonify(_format_convo(synthetic))

    return jsonify({"error": "Not found"}), 404


@conversations_bp.route("/api/convos/update", methods=["POST"])
@require_jwt
def update_conversation():
    data = request.get_json() or {}
    arg = data.get("arg", {})
    conversation_id = arg.get("conversationId")
    if not conversation_id:
        return jsonify({"error": "conversationId required"}), 400

    assistant_id = get_user_assistant_id(g.user_id)
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

    assistant_id = get_user_assistant_id(g.user_id)
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

    assistant_id = get_user_assistant_id(g.user_id)
    config_assistant_id = get_user_config_assistant_id(g.user_id)

    # If the conversation belongs to a folder, also remove its thread_mapping from
    # the folder's BB assistant so it disappears from the folder listing.
    convos = list_conversations(assistant_id)
    existing = next((c for c in convos if c.get("conversationId") == conversation_id), None)
    folder_id = (existing or {}).get("folderId", "")
    if folder_id:
        folder_bb_assistant_id = run_async(_get_bb_assistant_id_for_folder(config_assistant_id, folder_id))
        if folder_bb_assistant_id:
            remove_thread_mapping(folder_bb_assistant_id, conversation_id)

    delete_conversation_meta(assistant_id, conversation_id)
    return jsonify({"message": "Deleted"})


async def _get_bb_assistant_id_for_folder(config_assistant_id: str, folder_id: str) -> str:
    """Scan config assistant memories for a folder's bb_assistant_id."""
    client = get_client()
    resp = await client.get_memories(config_assistant_id)
    for m in resp.memories:
        meta = m.metadata or {}
        if meta.get("type") != "folder":
            continue
        try:
            data = json.loads(m.content)
        except (json.JSONDecodeError, Exception):
            continue
        if data.get("folderId") == folder_id:
            return data.get("bb_assistant_id", "")
    return ""


async def _find_folder_for_conversation(config_assistant_id: str, conversation_id: str) -> tuple[str, str]:
    """Scan all folder BB assistants to find which one has a thread_mapping for conversation_id.

    Returns (folder_id, folder_bb_assistant_id), or ("", "") if not found.
    """
    from api.routes.folders import _list_folders
    client = get_client()
    folders = await _list_folders(config_assistant_id)
    for f in folders:
        bb_aid = f.get("bb_assistant_id", "")
        if not bb_aid:
            continue
        resp = await client.get_memories(bb_aid)
        for m in resp.memories:
            meta = m.metadata or {}
            if meta.get("type") == "thread_mapping" and meta.get("conversationId") == conversation_id:
                return f.get("folderId", ""), bb_aid
    return "", ""


@conversations_bp.route("/api/convos/gen_title/<conversation_id>", methods=["GET"])
@require_jwt
def gen_title(conversation_id):
    assistant_id = get_user_assistant_id(g.user_id)
    config_assistant_id = get_user_config_assistant_id(g.user_id)

    thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)

    if not thread_id:
        # Conversation may live in a folder with its own BB assistant whose thread
        # mappings haven't been loaded into the in-process cache yet (e.g. after restart).
        convos = list_conversations(assistant_id)
        convo_meta = next((c for c in convos if c.get("conversationId") == conversation_id), None)
        folder_id = (convo_meta or {}).get("folderId")
        if folder_id:
            folder_bb_assistant_id = run_async(
                _get_bb_assistant_id_for_folder(config_assistant_id, folder_id)
            )
            if folder_bb_assistant_id:
                thread_id = get_thread_id_for_conversation(
                    conversation_id, assistant_id=folder_bb_assistant_id
                )

    if not thread_id:
        return jsonify({"title": "New Chat"})

    async def _generate():
        client = get_client()
        messages = await get_thread_messages(thread_id)
        if not messages:
            return "New Chat"
        first_user = ""
        first_assistant = ""
        for m in messages[:4]:
            if m.role == "user" and not first_user:
                first_user = (m.content or "")[:200]
            elif m.role == "assistant" and not first_assistant:
                first_assistant = (m.content or "")[:200]
        snippet = first_user or first_assistant or "New Chat"
        title_thread = await client.create_thread(assistant_id)
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
        save_conversation_meta(assistant_id, conversation_id, {"title": title})
    elif not title:
        title = "New Chat"

    return jsonify({"title": title})


@conversations_bp.route("/api/convos/fork", methods=["POST"])
@require_jwt
def fork_conversation():
    data = request.get_json() or {}
    message_id = data.get("messageId")
    conversation_id = data.get("conversationId")
    split_at_target = data.get("splitAtTarget", False)

    if not message_id or not conversation_id:
        return jsonify({"error": "messageId and conversationId required"}), 400

    assistant_id = get_user_assistant_id(g.user_id)
    src_thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)
    if not src_thread_id:
        return jsonify({"error": "Source conversation not found"}), 404

    source_convos = list_conversations(assistant_id)
    src_meta = next((c for c in source_convos if c.get("conversationId") == conversation_id), {})

    async def _fetch_src():
        return await get_thread_messages(src_thread_id)

    src_messages = run_async(_fetch_src())

    target_idx = len(src_messages) - 1
    for i, m in enumerate(src_messages):
        if str(m.message_id) == message_id:
            target_idx = i
            break

    sliced = src_messages[target_idx:] if split_at_target else src_messages[:target_idx + 1]

    new_conversation_id = str(uuid.uuid4())
    get_or_create_thread(assistant_id, new_conversation_id)

    snapshot = _build_message_snapshot(sliced, new_conversation_id)

    now = datetime.now(timezone.utc).isoformat()
    fork_meta = {
        "conversationId": new_conversation_id,
        "title": f"Fork: {src_meta.get('title', 'New Chat')}",
        "endpoint": src_meta.get("endpoint", "agents"),
        "model": src_meta.get("model", ""),
        "createdAt": now,
        "updatedAt": now,
        "forked_from": conversation_id,
        "forked_messages": snapshot,
    }
    save_conversation_meta(assistant_id, new_conversation_id, fork_meta)

    return jsonify({"conversation": _format_convo(fork_meta), "messages": snapshot})


@conversations_bp.route("/api/convos/duplicate", methods=["POST"])
@require_jwt
def duplicate_conversation():
    data = request.get_json() or {}
    conversation_id = data.get("conversationId")
    if not conversation_id:
        return jsonify({"error": "conversationId required"}), 400

    assistant_id = get_user_assistant_id(g.user_id)
    src_thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)
    if not src_thread_id:
        return jsonify({"error": "Source conversation not found"}), 404

    source_convos = list_conversations(assistant_id)
    src_meta = next((c for c in source_convos if c.get("conversationId") == conversation_id), {})

    async def _fetch_src():
        return await get_thread_messages(src_thread_id)

    src_messages = run_async(_fetch_src())

    new_conversation_id = str(uuid.uuid4())
    get_or_create_thread(assistant_id, new_conversation_id)

    snapshot = _build_message_snapshot(src_messages, new_conversation_id)

    now = datetime.now(timezone.utc).isoformat()
    dup_meta = {
        "conversationId": new_conversation_id,
        "title": f"Copy: {src_meta.get('title', 'New Chat')}",
        "endpoint": src_meta.get("endpoint", "agents"),
        "model": src_meta.get("model", ""),
        "createdAt": now,
        "updatedAt": now,
        "forked_from": conversation_id,
        "forked_messages": snapshot,
    }
    save_conversation_meta(assistant_id, new_conversation_id, dup_meta)

    return jsonify({"conversation": _format_convo(dup_meta), "messages": snapshot})


@conversations_bp.route("/api/convos/<conversation_id>/folder", methods=["PUT"])
@require_jwt
def move_to_folder(conversation_id):
    """
    Move a conversation into (or out of) a folder using the create/copy/hide approach:
      - Into folder: write thread_mapping on folder's BB assistant + mark conv_meta hidden.
      - Out of folder: remove thread_mapping from folder's BB assistant + unhide conv_meta.
    No messages are copied; the existing Backboard thread is reused.
    """
    data = request.get_json() or {}
    folder_id = data.get("folderId")  # None / "" means remove from current folder

    assistant_id = get_user_assistant_id(g.user_id)
    config_assistant_id = get_user_config_assistant_id(g.user_id)

    # Resolve existing conversation metadata.
    convos = list_conversations(assistant_id)
    convo_meta = next((c for c in convos if c.get("conversationId") == conversation_id), None)
    if not convo_meta:
        return jsonify({"error": "Not found"}), 404

    current_folder_id = convo_meta.get("folderId", "")

    # Remove from current folder if the conversation was already in one.
    if current_folder_id:
        current_bb_id = run_async(_get_bb_assistant_id_for_folder(config_assistant_id, current_folder_id))
        if current_bb_id:
            remove_thread_mapping(current_bb_id, conversation_id)

    if folder_id:
        # Resolve the target folder's BB assistant.
        folder_bb_assistant_id = run_async(_get_bb_assistant_id_for_folder(config_assistant_id, folder_id))
        if not folder_bb_assistant_id:
            return jsonify({"error": "Target folder not found or has no isolated assistant"}), 404

        # Resolve the existing thread_id for this conversation.
        thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)
        if not thread_id:
            return jsonify({"error": "Thread not found for conversation"}), 404

        # Write a thread_mapping on the folder's BB assistant pointing at the existing thread.
        add_thread_mapping(folder_bb_assistant_id, conversation_id, thread_id)

        # Hide conversation from the main list and record its folder.
        updated_meta = {**convo_meta, "folderId": folder_id, "hidden": True}
        save_conversation_meta(assistant_id, conversation_id, updated_meta)
    else:
        # Moving out of folder: unhide and clear folderId.
        updated_meta = {k: v for k, v in convo_meta.items() if k not in ("folderId", "hidden")}
        save_conversation_meta(assistant_id, conversation_id, updated_meta)

    return jsonify(_format_convo(updated_meta))


def _build_message_snapshot(messages: list, conversation_id: str) -> list:
    """Convert a list of Backboard message objects into the UI message format."""
    snapshot = []
    prev_id = "00000000-0000-0000-0000-000000000000"
    for m in messages:
        msg = {
            "messageId": str(m.message_id),
            "conversationId": conversation_id,
            "parentMessageId": prev_id,
            "text": m.content or "",
            "sender": "User" if m.role == "user" else "Nash",
            "isCreatedByUser": m.role == "user",
            "endpoint": "agents",
            "createdAt": m.created_at.isoformat() if m.created_at else "",
            "updatedAt": m.created_at.isoformat() if m.created_at else "",
            "error": False,
        }
        snapshot.append(msg)
        prev_id = msg["messageId"]
    return snapshot


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
