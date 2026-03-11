from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_thread_messages
from api.services.async_runner import run_async
from api.services.user_service import get_user_assistant_id
from api.services.conversation_service import (
    get_thread_id_for_conversation,
    list_conversations,
    get_conversation_forked_messages,
    get_regen_graph,
)

messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/api/messages", methods=["GET"])
@require_jwt
def search_messages():
    """Search messages across all conversations by text content."""
    search_query = (request.args.get("search") or "").lower().strip()
    if not search_query:
        return jsonify({"messages": [], "nextCursor": None})

    assistant_id = get_user_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)

    matched_messages = []
    for convo in convos:
        conversation_id = convo.get("conversationId", "")
        if not conversation_id:
            continue

        thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)
        if not thread_id:
            continue

        async def _fetch(tid=thread_id):
            return await get_thread_messages(tid)

        try:
            bb_messages = run_async(_fetch())
        except Exception:
            continue

        for m in bb_messages:
            text = m.content or ""
            if search_query in text.lower():
                matched_messages.append({
                    "messageId": str(m.message_id),
                    "conversationId": conversation_id,
                    "parentMessageId": "00000000-0000-0000-0000-000000000000",
                    "text": text,
                    "title": convo.get("title", "New Chat"),
                    "sender": "User" if m.role == "user" else "Nash",
                    "isCreatedByUser": m.role == "user",
                    "endpoint": "agents",
                    "createdAt": m.created_at.isoformat() if m.created_at else "",
                    "updatedAt": m.created_at.isoformat() if m.created_at else "",
                    "error": False,
                })

    return jsonify({"messages": matched_messages, "nextCursor": None})


@messages_bp.route("/api/messages/<conversation_id>", methods=["GET"])
@require_jwt
def get_messages(conversation_id):
    assistant_id = get_user_assistant_id(g.user_id)
    thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)
    if not thread_id:
        return jsonify([])

    forked_snapshot = get_conversation_forked_messages(assistant_id, conversation_id)

    async def _fetch():
        return await get_thread_messages(thread_id)

    bb_messages = run_async(_fetch())

    if forked_snapshot:
        messages = list(forked_snapshot)
        last_id = messages[-1]["messageId"] if messages else "00000000-0000-0000-0000-000000000000"
        for m in bb_messages:
            msg = {
                "messageId": str(m.message_id),
                "conversationId": conversation_id,
                "parentMessageId": last_id,
                "text": m.content or "",
                "sender": "User" if m.role == "user" else "Nash",
                "isCreatedByUser": m.role == "user",
                "endpoint": "agents",
                "createdAt": m.created_at.isoformat() if m.created_at else "",
                "updatedAt": m.created_at.isoformat() if m.created_at else "",
                "error": False,
            }
            messages.append(msg)
            last_id = msg["messageId"]
        return jsonify(messages)

    regen_graph = get_regen_graph(assistant_id, conversation_id)

    messages = []
    for m in bb_messages:
        bb_id = str(m.message_id)
        if regen_graph.get(bb_id) == "SKIP":
            continue
        messages.append({
            "messageId": bb_id,
            "conversationId": conversation_id,
            "parentMessageId": "00000000-0000-0000-0000-000000000000",
            "text": m.content or "",
            "sender": "User" if m.role == "user" else "Nash",
            "isCreatedByUser": m.role == "user",
            "endpoint": "agents",
            "createdAt": m.created_at.isoformat() if m.created_at else "",
            "updatedAt": m.created_at.isoformat() if m.created_at else "",
            "error": False,
        })

    # Build linear parent chain first
    if len(messages) >= 2:
        for i in range(1, len(messages)):
            messages[i]["parentMessageId"] = messages[i - 1]["messageId"]

    # Apply persisted parent overrides (regenerated AI responses share the original user as parent)
    if regen_graph:
        for msg in messages:
            override = regen_graph.get(msg["messageId"])
            if override and override != "SKIP":
                msg["parentMessageId"] = override

    return jsonify(messages)


@messages_bp.route("/api/messages/<conversation_id>/<message_id>", methods=["GET"])
@require_jwt
def get_message(conversation_id, message_id):
    return jsonify({"messageId": message_id, "conversationId": conversation_id})


@messages_bp.route("/api/messages/<conversation_id>/<message_id>", methods=["PUT"])
@require_jwt
def update_message(conversation_id, message_id):
    return jsonify({"messageId": message_id, "conversationId": conversation_id})


@messages_bp.route("/api/messages/<conversation_id>/<message_id>", methods=["DELETE"])
@require_jwt
def delete_message(conversation_id, message_id):
    return jsonify({"message": "Deleted"})


@messages_bp.route("/api/messages/<conversation_id>/<message_id>/feedback", methods=["POST"])
@require_jwt
def message_feedback(conversation_id, message_id):
    return jsonify({"message": "ok"})


@messages_bp.route("/api/messages/branch", methods=["POST"])
@require_jwt
def branch_messages():
    return jsonify({"error": "Not implemented"}), 501
