from flask import Blueprint, request, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.user_service import get_user_config_assistant_id
from api.services.conversation_service import list_conversations

search_bp = Blueprint("search", __name__)


@search_bp.route("/api/search", methods=["GET"])
@require_jwt
def search_conversations():
    q = request.args.get("q", "").lower().strip()
    if not q:
        return jsonify({
            "conversations": [],
            "messages": [],
            "pageNumber": "1",
            "pageSize": 25,
            "pages": 0,
        })

    assistant_id = get_user_config_assistant_id(g.user_id)
    convos = list_conversations(assistant_id)

    matches = []
    for c in convos:
        title = (c.get("title") or "").lower()
        if q in title:
            matches.append({
                "conversationId": c.get("conversationId", ""),
                "title": c.get("title", "New Chat"),
                "endpoint": c.get("endpoint", "custom"),
                "model": c.get("model", ""),
                "createdAt": c.get("createdAt", ""),
                "updatedAt": c.get("updatedAt", ""),
            })

    page_size = int(request.args.get("pageSize", "25"))
    page_number = int(request.args.get("pageNumber", "1"))
    start = (page_number - 1) * page_size
    page = matches[start:start + page_size]
    total_pages = max(1, (len(matches) + page_size - 1) // page_size)

    return jsonify({
        "conversations": page,
        "messages": [],
        "pageNumber": str(page_number),
        "pageSize": page_size,
        "pages": total_pages,
    })


@search_bp.route("/api/search/enable", methods=["GET"])
@require_jwt
def search_enabled():
    return jsonify({"enabled": True})
