import json

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id
from api.services.conversation_service import list_conversations, save_conversation_meta

tags_bp = Blueprint("tags", __name__)

TAG_META_TYPE = "tag"


async def _list_tags(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    tags = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != TAG_META_TYPE:
            continue
        try:
            t = json.loads(m.content)
            t["_memory_id"] = m.id
            tags.append(t)
        except json.JSONDecodeError:
            continue
    return tags


async def _update_tag_count(assistant_id: str, tag_name: str, delta: int) -> None:
    """Increment or decrement a tag's conversation count. Does nothing if tag not found."""
    client = get_client()
    all_tags = await _list_tags(assistant_id)
    for t in all_tags:
        if t.get("tag") != tag_name:
            continue
        memory_id = t.get("_memory_id")
        if not memory_id:
            continue
        new_count = max(0, t.get("count", 0) + delta)
        new_content = {**t, "count": new_count}
        del new_content["_memory_id"]
        meta = {"type": TAG_META_TYPE, "tag": tag_name}
        await client.update_memory(
            assistant_id=assistant_id,
            memory_id=memory_id,
            content=json.dumps(new_content),
            metadata=meta,
        )
        return


@tags_bp.route("/api/tags", methods=["GET"])
@require_jwt
def get_tags():
    assistant_id = get_user_config_assistant_id(g.user_id)
    tags = run_async(_list_tags(assistant_id))
    return jsonify([{k: v for k, v in t.items() if k != "_memory_id"} for t in tags])


@tags_bp.route("/api/tags/list", methods=["GET"])
@require_jwt
def list_tags():
    assistant_id = get_user_config_assistant_id(g.user_id)
    tags = run_async(_list_tags(assistant_id))
    return jsonify([{k: v for k, v in t.items() if k != "_memory_id"} for t in tags])


@tags_bp.route("/api/tags", methods=["POST"])
@require_jwt
def create_tag():
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    tag = {"tag": data.get("tag", ""), "count": 0}

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(tag),
            metadata={"type": TAG_META_TYPE, "tag": tag["tag"]},
        )

    run_async(_save())
    return jsonify(tag)


@tags_bp.route("/api/tags/<tag>", methods=["DELETE"])
@require_jwt
def delete_tag(tag):
    assistant_id = get_user_config_assistant_id(g.user_id)
    tags = run_async(_list_tags(assistant_id))
    for t in tags:
        if t.get("tag") == tag:
            memory_id = t.get("_memory_id")
            if memory_id:
                async def _del():
                    client = get_client()
                    await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)
                run_async(_del())
            return jsonify({"message": "Deleted"})
    return jsonify({"error": "Not found"}), 404


@tags_bp.route("/api/tags/convo/<conversation_id>", methods=["POST"])
@require_jwt
def add_tag_to_convo(conversation_id):
    data = request.get_json() or {}
    tags = data.get("tags", [])
    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)
    existing = None
    for c in convos:
        if c.get("conversationId") == conversation_id:
            existing = c
            break
    old_tags = set(existing.get("tags", [])) if existing else set()
    new_tags = set(tags)
    added = new_tags - old_tags
    removed = old_tags - new_tags

    meta = existing or {"conversationId": conversation_id}
    meta["tags"] = tags
    save_conversation_meta(assistant_id, conversation_id, meta)

    async def _update_counts():
        for tag_name in added:
            await _update_tag_count(assistant_id, tag_name, 1)
        for tag_name in removed:
            await _update_tag_count(assistant_id, tag_name, -1)

    run_async(_update_counts())
    return jsonify({"conversationId": conversation_id, "tags": tags})
