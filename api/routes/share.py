import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from api.config import settings
from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_assistant_id
from api.services.conversation_service import get_thread_id_for_conversation

share_bp = Blueprint("share", __name__)

SHARE_META_TYPE = "shared_link"
_GLOBAL_ASSISTANT_ID = settings.backboard_assistant_id


def _format_bb_messages(bb_messages, conversation_id: str) -> list[dict]:
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
    return messages


async def _list_all_shares() -> list[dict]:
    """Load all share records from the global assistant."""
    client = get_client()
    response = await client.get_memories(_GLOBAL_ASSISTANT_ID)
    shares = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != SHARE_META_TYPE:
            continue
        try:
            s = json.loads(m.content)
            s["_memory_id"] = m.id
            shares.append(s)
        except json.JSONDecodeError:
            continue
    return shares


async def _find_share_by_id(share_id: str) -> dict | None:
    shares = await _list_all_shares()
    for s in shares:
        if s.get("shareId") == share_id:
            return s
    return None


@share_bp.route("/api/share/<share_id>", methods=["GET"])
def get_share(share_id):
    share = run_async(_find_share_by_id(share_id))
    if not share or not share.get("isPublic"):
        return jsonify({"error": "Not found"}), 404

    conversation_id = share.get("conversationId", "")
    user_id = share.get("userId", "")
    messages = []

    if conversation_id and user_id:
        try:
            user_assistant_id = get_user_assistant_id(user_id)
            thread_id = get_thread_id_for_conversation(conversation_id, assistant_id=user_assistant_id)
            if thread_id:
                async def _fetch():
                    client = get_client()
                    thread = await client.get_thread(thread_id)
                    return thread.messages

                bb_messages = run_async(_fetch())
                messages = _format_bb_messages(bb_messages, conversation_id)
        except Exception:
            pass

    return jsonify({
        "shareId": share.get("shareId"),
        "conversationId": conversation_id,
        "title": share.get("title", ""),
        "isPublic": share.get("isPublic", True),
        "createdAt": share.get("createdAt", ""),
        "updatedAt": share.get("updatedAt", ""),
        "messages": messages,
    })


@share_bp.route("/api/share", methods=["GET"])
@require_jwt
def list_shares():
    shares = run_async(_list_all_shares())
    user_shares = [
        {k: v for k, v in s.items() if k != "_memory_id"}
        for s in shares
        if s.get("userId") == g.user_id
    ]
    return jsonify({
        "sharedLinks": user_shares,
        "pageSize": 25,
        "pages": max(1, (len(user_shares) + 24) // 25),
    })


@share_bp.route("/api/share/link/<conversation_id>", methods=["GET"])
@require_jwt
def get_share_link(conversation_id):
    shares = run_async(_list_all_shares())
    for s in shares:
        if s.get("conversationId") == conversation_id and s.get("userId") == g.user_id and s.get("isPublic"):
            return jsonify({k: v for k, v in s.items() if k != "_memory_id"})
    return jsonify({"conversationId": conversation_id, "shareId": None, "isPublic": False})


@share_bp.route("/api/share/<conversation_id>", methods=["POST"])
@require_jwt
def create_share(conversation_id):
    share_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    title = "Shared Chat"
    try:
        from api.services.conversation_service import list_conversations
        user_assistant_id = get_user_assistant_id(g.user_id)
        for c in list_conversations(user_assistant_id):
            if c.get("conversationId") == conversation_id:
                title = c.get("title", "Shared Chat")
                break
    except Exception:
        pass

    share = {
        "shareId": share_id,
        "conversationId": conversation_id,
        "userId": g.user_id,
        "title": title,
        "isPublic": True,
        "createdAt": now,
        "updatedAt": now,
    }

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=_GLOBAL_ASSISTANT_ID,
            content=json.dumps(share),
            metadata={
                "type": SHARE_META_TYPE,
                "shareId": share_id,
                "conversationId": conversation_id,
                "userId": g.user_id,
            },
        )

    run_async(_save())
    return jsonify({k: v for k, v in share.items() if k != "userId"})


@share_bp.route("/api/share/<share_id>", methods=["PATCH"])
@require_jwt
def update_share(share_id):
    data = request.get_json() or {}
    share = run_async(_find_share_by_id(share_id))

    if not share or share.get("userId") != g.user_id:
        return jsonify({"error": "Not found"}), 404

    memory_id = share.get("_memory_id")
    if "isPublic" in data:
        share["isPublic"] = data["isPublic"]
    share["updatedAt"] = datetime.now(timezone.utc).isoformat()

    async def _update():
        client = get_client()
        content = {k: v for k, v in share.items() if k != "_memory_id"}
        await client.update_memory(
            assistant_id=_GLOBAL_ASSISTANT_ID,
            memory_id=memory_id,
            content=json.dumps(content),
            metadata={
                "type": SHARE_META_TYPE,
                "shareId": share_id,
                "conversationId": share.get("conversationId", ""),
                "userId": g.user_id,
            },
        )

    run_async(_update())
    return jsonify({k: v for k, v in share.items() if k not in ("_memory_id", "userId")})


@share_bp.route("/api/share/<share_id>", methods=["DELETE"])
@require_jwt
def delete_share(share_id):
    share = run_async(_find_share_by_id(share_id))

    if not share or share.get("userId") != g.user_id:
        return jsonify({"error": "Not found"}), 404

    memory_id = share.get("_memory_id")

    async def _delete():
        client = get_client()
        await client.delete_memory(assistant_id=_GLOBAL_ASSISTANT_ID, memory_id=memory_id)

    run_async(_delete())
    return jsonify({"message": "Deleted"})
