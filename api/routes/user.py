from flask import Blueprint, jsonify, g

from api.middleware.jwt_auth import require_jwt
from api.services.user_service import find_user_by_id

user_bp = Blueprint("user", __name__)


@user_bp.route("/api/user", methods=["GET"])
@require_jwt
def get_user():
    user = find_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "id": user["id"],
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "username": user.get("username", ""),
        "avatar": user.get("avatar", ""),
        "provider": user.get("provider", ""),
        "role": user.get("role", "USER"),
        "createdAt": user.get("createdAt", ""),
        "updatedAt": user.get("updatedAt", ""),
    })


@user_bp.route("/api/user/terms", methods=["GET"])
@require_jwt
def get_terms():
    return jsonify({"termsOfService": None, "privacyPolicy": None})


@user_bp.route("/api/user/terms/accept", methods=["POST"])
@require_jwt
def accept_terms():
    return jsonify({"message": "ok"})


@user_bp.route("/api/balance", methods=["GET"])
@require_jwt
def get_balance():
    return jsonify({"balance": 1000000})
