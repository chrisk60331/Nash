import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id
from api.services.conversation_service import list_conversations, get_thread_id_for_conversation

share_bp = Blueprint("share", __name__)

SHARE_META_TYPE = "shared_link"


async def _list_shares(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
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


@share_bp.route("/api/share", methods=["GET"])
@require_jwt
def list_shares():
    assistant_id = get_user_config_assistant_id(g.user_id)
    shares = run_async(_list_shares(assistant_id))
    return jsonify({
        "sharedLinks": [{k: v for k, v in s.items() if k != "_memory_id"} for s in shares],
        "pageSize": 25,
        "pages": max(1, (len(shares) + 24) // 25),
    })


@share_bp.route("/api/share/<share_id>", methods=["GET"])
def get_share(share_id):
    return jsonify({"error": "Not found"}), 404


@share_bp.route("/api/share/link/<conversation_id>", methods=["GET"])
@require_jwt
def get_share_link(conversation_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    shares = run_async(_list_shares(assistant_id))
    for s in shares:
        if s.get("conversationId") == conversation_id and s.get("isPublic"):
            return jsonify({k: v for k, v in s.items() if k != "_memory_id"})
    return jsonify({"conversationId": conversation_id, "shareId": None, "isPublic": False})


@share_bp.route("/api/share/<conversation_id>", methods=["POST"])
@require_jwt
def create_share(conversation_id):
    assistant_id = get_user_config_assistant_id(g.user_id)

    convos = list_conversations(assistant_id)
    convo = None
    for c in convos:
        if c.get("conversationId") == conversation_id:
            convo = c
            break

    share_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    share = {
        "shareId": share_id,
        "conversationId": conversation_id,
        "title": (convo or {}).get("title", "Shared Chat"),
        "isPublic": True,
        "createdAt": now,
        "updatedAt": now,
    }

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(share),
            metadata={
                "type": SHARE_META_TYPE,
                "shareId": share_id,
                "conversationId": conversation_id,
            },
        )

    run_async(_save())
    return jsonify(share)


@share_bp.route("/api/share/<share_id>", methods=["PATCH"])
@require_jwt
def update_share(share_id):
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    shares = run_async(_list_shares(assistant_id))

    for s in shares:
        if s.get("shareId") == share_id:
            memory_id = s.get("_memory_id")
            if "isPublic" in data:
                s["isPublic"] = data["isPublic"]
            s["updatedAt"] = datetime.now(timezone.utc).isoformat()

            async def _update():
                client = get_client()
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps({k: v for k, v in s.items() if k != "_memory_id"}),
                    metadata={
                        "type": SHARE_META_TYPE,
                        "shareId": share_id,
                        "conversationId": s.get("conversationId", ""),
                    },
                )

            run_async(_update())
            return jsonify({k: v for k, v in s.items() if k != "_memory_id"})

    return jsonify({"error": "Not found"}), 404
