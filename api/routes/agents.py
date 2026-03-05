import json
import logging
import uuid

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id

logger = logging.getLogger(__name__)

agents_bp = Blueprint("agents", __name__)

AGENT_META_TYPE = "agent"


async def _list_agents(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    agents = []
    needs_update = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != AGENT_META_TYPE:
            continue
        try:
            a = json.loads(m.content)
            a["_memory_id"] = m.id
        except json.JSONDecodeError:
            continue
        dirty = False
        old_id = a.get("id", "")
        if old_id and not old_id.startswith("agent_"):
            a["id"] = f"agent_{old_id}"
            dirty = True
        if not a.get("bb_assistant_id"):
            bb = await client.create_assistant(
                name=f"nash-agent-{a['id']}",
                system_prompt=a.get("instructions", ""),
            )
            a["bb_assistant_id"] = str(bb.assistant_id)
            logger.warning("[agents] migration: created Backboard assistant %s for agent %s", a["bb_assistant_id"], a["id"])
            dirty = True
        if dirty:
            needs_update.append(a)
        agents.append(a)

    for a in needs_update:
        memory_id = a.get("_memory_id")
        if not memory_id:
            continue
        content = {k: v for k, v in a.items() if not k.startswith("_")}
        try:
            await client.update_memory(
                assistant_id=assistant_id,
                memory_id=memory_id,
                content=json.dumps(content),
                metadata={"type": AGENT_META_TYPE, "agentId": content["id"]},
            )
        except Exception:
            logger.exception("[agents] migration: failed to persist agent %s", a.get("id"))

    return agents


@agents_bp.route("/api/agents", methods=["GET"])
@require_jwt
def list_agents():
    assistant_id = get_user_config_assistant_id(g.user_id)
    agents = run_async(_list_agents(assistant_id))
    cleaned = [{k: v for k, v in a.items() if k != "_memory_id"} for a in agents]
    return jsonify({
        "object": "list",
        "data": cleaned,
        "first_id": cleaned[0]["id"] if cleaned else "",
        "last_id": cleaned[-1]["id"] if cleaned else "",
        "has_more": False,
    })


@agents_bp.route("/api/agents", methods=["POST"])
@require_jwt
def create_agent():
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    agent_id = data.get("id") or f"agent_{uuid.uuid4()}"
    data["id"] = agent_id

    async def _save():
        client = get_client()
        bb_assistant = await client.create_assistant(
            name=f"nash-agent-{agent_id}",
            system_prompt=data.get("instructions", ""),
        )
        data["bb_assistant_id"] = str(bb_assistant.assistant_id)
        logger.warning("[agents] created Backboard assistant %s for agent %s", data["bb_assistant_id"], agent_id)
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(data),
            metadata={"type": AGENT_META_TYPE, "agentId": agent_id},
        )

    run_async(_save())
    return jsonify(data), 201


@agents_bp.route("/api/agents/<agent_id>", methods=["GET"])
@agents_bp.route("/api/agents/<agent_id>/expanded", methods=["GET"])
@require_jwt
def get_agent(agent_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    agents = run_async(_list_agents(assistant_id))
    for a in agents:
        if a.get("id") == agent_id:
            return jsonify({k: v for k, v in a.items() if k != "_memory_id"})
    return jsonify({"error": "Not found"}), 404


@agents_bp.route("/api/agents/<agent_id>", methods=["PATCH"])
@require_jwt
def update_agent(agent_id):
    data = request.get_json() or {}
    assistant_id = get_user_config_assistant_id(g.user_id)
    agents = run_async(_list_agents(assistant_id))

    for a in agents:
        if a.get("id") == agent_id:
            memory_id = a.get("_memory_id")
            bb_assistant_id = a.get("bb_assistant_id", "")
            a.update({k: v for k, v in data.items() if k != "_memory_id"})

            async def _update():
                client = get_client()
                content = {k: v for k, v in a.items() if not k.startswith("_")}
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps(content),
                    metadata={"type": AGENT_META_TYPE, "agentId": agent_id},
                )
                if bb_assistant_id and "instructions" in data:
                    await client.update_assistant(
                        bb_assistant_id,
                        system_prompt=data["instructions"] or "",
                    )
                    logger.warning("[agents] synced system_prompt to Backboard assistant %s", bb_assistant_id)

            run_async(_update())
            return jsonify({k: v for k, v in a.items() if not k.startswith("_")})

    return jsonify({"error": "Not found"}), 404


@agents_bp.route("/api/agents/<agent_id>", methods=["DELETE"])
@require_jwt
def delete_agent(agent_id):
    assistant_id = get_user_config_assistant_id(g.user_id)
    agents = run_async(_list_agents(assistant_id))
    for a in agents:
        if a.get("id") == agent_id:
            memory_id = a.get("_memory_id")
            if memory_id:
                async def _del():
                    client = get_client()
                    await client.delete_memory(assistant_id=assistant_id, memory_id=memory_id)
                run_async(_del())
            return jsonify({"message": "Deleted"})
    return jsonify({"error": "Not found"}), 404


@agents_bp.route("/api/categories", methods=["GET"])
@agents_bp.route("/api/agents/categories", methods=["GET"])
def get_categories():
    return jsonify([])


@agents_bp.route("/api/agents/tools", methods=["GET"])
@require_jwt
def agent_tools():
    return jsonify([])


@agents_bp.route("/api/agents/actions", methods=["GET"])
@require_jwt
def agent_actions():
    return jsonify([])


@agents_bp.route("/api/files/agent/<agent_id>", methods=["GET"])
@require_jwt
def agent_files(agent_id):
    return jsonify([])
