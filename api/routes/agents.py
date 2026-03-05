import json
import uuid

from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_config_assistant_id

agents_bp = Blueprint("agents", __name__)

AGENT_META_TYPE = "agent"


async def _list_agents(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    agents = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != AGENT_META_TYPE:
            continue
        try:
            a = json.loads(m.content)
            a["_memory_id"] = m.id
            agents.append(a)
        except json.JSONDecodeError:
            continue
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
    agent_id = data.get("id") or str(uuid.uuid4())
    data["id"] = agent_id

    async def _save():
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(data),
            metadata={"type": AGENT_META_TYPE, "agentId": agent_id},
        )

    run_async(_save())
    return jsonify(data), 201


@agents_bp.route("/api/agents/<agent_id>", methods=["GET"])
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
            a.update({k: v for k, v in data.items() if k != "_memory_id"})

            async def _update():
                client = get_client()
                await client.update_memory(
                    assistant_id=assistant_id,
                    memory_id=memory_id,
                    content=json.dumps({k: v for k, v in a.items() if k != "_memory_id"}),
                    metadata={"type": AGENT_META_TYPE, "agentId": agent_id},
                )

            run_async(_update())
            return jsonify({k: v for k, v in a.items() if k != "_memory_id"})

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
