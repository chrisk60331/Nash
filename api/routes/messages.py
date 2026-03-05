from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id
from api.services.conversation_service import get_thread_id_for_conversation

messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/api/messages/<conversation_id>", methods=["GET"])
@require_jwt
def get_messages(conversation_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=assistant_id)
    if not thread_id:
        return jsonify([])

    async def _fetch():
        client = get_client()
        thread = await client.get_thread(thread_id)
        return thread.messages

    bb_messages = run_async(_fetch())
    messages = []
    for m in bb_messages:
        messages.append({
            "messageId": str(m.message_id),
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

    if len(messages) >= 2:
        for i in range(1, len(messages)):
            messages[i]["parentMessageId"] = messages[i - 1]["messageId"]

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
