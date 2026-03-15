from datetime import datetime, timezone
import json

from datetime import datetime, timezone

import stripe
from flask import Blueprint, jsonify, request, g, make_response

from api.config import settings
from api.middleware.jwt_auth import require_jwt
from api.services import audit_service
from api.services.user_service import (
    find_user_by_id, update_user_field, get_user_assistant_id, get_user_config_assistant_id, delete_user,
)
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services import conversation_service
from api.services.balance_service import get_balance_response

stripe.api_key = settings.stripe_secret_key

user_bp = Blueprint("user", __name__)

CHAT_DATA_TYPES = {"thread_mapping", "conversation_meta"}
USER_MEMORY_INTERNAL_TYPES = {
    "prompt", "prompt_group", "user_favorites",
    "file_meta", "agent", "shared_link",
    "tag", "folder", "preset",
    "user", "librechat_user", "user_memory",
}
FILE_META_TYPE = "file_meta"


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
        "nickname": user.get("nickname", ""),
        "avatar": user.get("avatar", ""),
        "provider": user.get("provider", ""),
        "role": user.get("role", "USER"),
        "twoFactorEnabled": user.get("twoFactorEnabled", False),
        "backupCodes": user.get("backupCodes", []),
        "createdAt": user.get("createdAt", ""),
        "updatedAt": user.get("updatedAt", ""),
    })


@user_bp.route("/api/user/profile", methods=["PATCH"])
@require_jwt
def update_profile():
    data = request.get_json() or {}
    user = find_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if "nickname" in data:
        nickname = str(data["nickname"]).strip()[:64]
        update_user_field(user, "nickname", nickname)
    return jsonify({
        "id": user["id"],
        "nickname": user.get("nickname", ""),
    })


@user_bp.route("/api/user/chat-data", methods=["DELETE"])
@require_jwt
def delete_chat_data():
    assistant_id = get_user_assistant_id(g.user_id)
    config_assistant_id = get_user_config_assistant_id(g.user_id)

    async def _delete_all():
        client = get_client()
        response = await client.get_memories(assistant_id)
        deleted = 0
        threads_deleted = 0
        documents_deleted = 0
        thread_ids: set[str] = set()
        for m in response.memories:
            meta = m.metadata or {}
            mem_type = meta.get("type", "")
            if mem_type == "thread_mapping":
                thread_id = meta.get("threadId") or ""
                if thread_id:
                    thread_ids.add(str(thread_id))
            if mem_type in CHAT_DATA_TYPES or mem_type not in USER_MEMORY_INTERNAL_TYPES:
                try:
                    await client.delete_memory(assistant_id=assistant_id, memory_id=m.id)
                    deleted += 1
                except Exception:
                    pass

        # Delete chat assistant threads after removing mappings
        for thread_id in thread_ids:
            try:
                await client._make_request("DELETE", f"threads/{thread_id}")
                threads_deleted += 1
            except Exception:
                pass

        # Delete live Backboard documents from the chat assistant (source of truth)
        try:
            live_docs = await client.list_assistant_documents(assistant_id)
            for doc in live_docs:
                try:
                    await client.delete_document(doc.document_id)
                    documents_deleted += 1
                except Exception:
                    pass
        except Exception:
            pass

        # Delete file_meta memory records from the config assistant (clears UI file list)
        if config_assistant_id:
            config_response = await client.get_memories(config_assistant_id)
            for m in config_response.memories:
                meta = m.metadata or {}
                if meta.get("type") != FILE_META_TYPE:
                    continue
                try:
                    await client.delete_memory(assistant_id=config_assistant_id, memory_id=m.id)
                    deleted += 1
                except Exception:
                    pass

        return {"deleted": deleted, "threads_deleted": threads_deleted, "documents_deleted": documents_deleted}

    result = run_async(_delete_all())
    # Clear in-memory thread cache for this assistant
    conversation_service._thread_map.clear()
    conversation_service._loaded_assistants.discard(assistant_id)
    audit_service.emit(
        "user.data_deleted",
        user_id=g.user_id,
        deleted_count=result.get("deleted", 0),
        threads_deleted=result.get("threads_deleted", 0),
        documents_deleted=result.get("documents_deleted", 0),
    )
    return jsonify({
        "message": f"Cleared {result.get('deleted', 0)} records",
        "threads_deleted": result.get("threads_deleted", 0),
        "documents_deleted": result.get("documents_deleted", 0),
    })


@user_bp.route("/api/user/terms", methods=["GET"])
@require_jwt
def get_terms():
    user = find_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    terms_accepted_at = user.get("termsAcceptedAt") or None
    return jsonify({
        "termsAccepted": terms_accepted_at is not None,
        "termsAcceptedAt": terms_accepted_at,
    })


@user_bp.route("/api/user/terms/accept", methods=["POST"])
@require_jwt
def accept_terms():
    user = find_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    accepted_at = datetime.now(timezone.utc).isoformat()
    update_user_field(user, "termsAcceptedAt", accepted_at)
    audit_service.emit("user.terms_accepted", user_id=g.user_id)
    return jsonify({"message": "ok", "termsAcceptedAt": accepted_at})


@user_bp.route("/api/user/chat-assistant", methods=["GET"])
@require_jwt
def get_chat_assistant():
    """Return the authenticated user's chat assistant system prompt."""
    try:
        assistant_id = get_user_assistant_id(g.user_id)
    except ValueError:
        return jsonify({"error": "User has no chat assistant"}), 404

    async def _fetch():
        client = get_client()
        assistant = await client.get_assistant(assistant_id)
        prompt = getattr(assistant, "system_prompt", None) or getattr(
            assistant, "instructions", None
        ) or ""
        return str(prompt) if prompt is not None else ""

    system_prompt = run_async(_fetch())
    return jsonify({"system_prompt": system_prompt})


@user_bp.route("/api/user/chat-assistant", methods=["PATCH"])
@require_jwt
def update_chat_assistant():
    """Update the authenticated user's chat assistant system prompt."""
    data = request.get_json(silent=True) or {}
    system_prompt = data.get("system_prompt")
    if system_prompt is None:
        return jsonify({"error": "system_prompt is required"}), 400
    system_prompt = str(system_prompt).strip()

    try:
        assistant_id = get_user_assistant_id(g.user_id)
    except ValueError:
        return jsonify({"error": "User has no chat assistant"}), 404

    async def _update():
        client = get_client()
        await client.update_assistant(
            assistant_id=assistant_id,
            system_prompt=system_prompt or "",
        )

    run_async(_update())
    audit_service.emit("user.chat_assistant_updated", user_id=g.user_id)
    return jsonify({"system_prompt": system_prompt or ""})


@user_bp.route("/api/user/account", methods=["DELETE"])
@require_jwt
def delete_account():
    """Permanent full account deletion (right to erasure).

    Order of operations:
      1. Cancel Stripe subscription (if active) — prevents future charges.
      2. Delete Backboard documents for user-uploaded files.
      3. Wipe all memories from the user's config Backboard assistant.
      4. Wipe all memories from the user's chat Backboard assistant.
      5. Delete the user's auth record from Backboard.
      6. Invalidate session (delete refresh token cookie).
      7. Emit audit event.
    """
    user = find_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # 1. Cancel Stripe subscription immediately
    stripe_sub_id = user.get("stripeSubscriptionId", "")
    if stripe_sub_id:
        try:
            stripe.Subscription.cancel(stripe_sub_id)
        except stripe.error.InvalidRequestError:
            pass  # Already cancelled / doesn't exist
        except Exception as e:
            audit_service.emit("user.account_delete.stripe_error", result="fail", user_id=g.user_id, error=str(e))

    async def _wipe_assistant(assistant_id: str) -> int:
        if not assistant_id:
            return 0
        client = get_client()
        response = await client.get_memories(assistant_id)
        deleted = 0
        for m in response.memories:
            try:
                await client.delete_memory(assistant_id=assistant_id, memory_id=m.id)
                deleted += 1
            except Exception:
                pass
        return deleted

    async def _delete_file_documents(assistant_id: str) -> dict:
        if not assistant_id:
            return {"documents_deleted": 0, "file_metas_deleted": 0}
        client = get_client()
        response = await client.get_memories(assistant_id)
        documents_deleted = 0
        file_metas_deleted = 0
        for m in response.memories:
            meta = m.metadata or {}
            if meta.get("type") != FILE_META_TYPE:
                continue
            try:
                content = json.loads(m.content)
            except json.JSONDecodeError:
                content = {}
            doc_id = content.get("document_id")
            if doc_id:
                try:
                    await client.delete_document(doc_id)
                    documents_deleted += 1
                except Exception:
                    pass
            try:
                await client.delete_memory(assistant_id=assistant_id, memory_id=m.id)
                file_metas_deleted += 1
            except Exception:
                pass
        return {"documents_deleted": documents_deleted, "file_metas_deleted": file_metas_deleted}

    # 2. Delete Backboard documents for user-uploaded files (source of truth)
    # 3 & 4. Wipe chat + config assistants
    chat_assistant_id = user.get("bbAssistantId", "")
    config_assistant_id = user.get("bbConfigAssistantId", "")

    file_deletes = run_async(_delete_file_documents(config_assistant_id))
    chat_deleted = run_async(_wipe_assistant(chat_assistant_id))
    config_deleted = run_async(_wipe_assistant(config_assistant_id))

    # Clear in-memory caches for this user
    conversation_service._thread_map.clear()
    if chat_assistant_id:
        conversation_service._loaded_assistants.discard(chat_assistant_id)

    # 4. Delete auth record from Backboard + evict from cache
    delete_user(user)

    audit_service.emit(
        "user.account_deleted",
        user_id=g.user_id,
        chat_records_deleted=chat_deleted,
        config_records_deleted=config_deleted,
        file_documents_deleted=file_deletes.get("documents_deleted", 0),
        file_metas_deleted=file_deletes.get("file_metas_deleted", 0),
    )

    # 5. Clear session cookie
    response = make_response(jsonify({"message": "Account permanently deleted"}))
    response.delete_cookie("refreshToken", path="/")
    return response


@user_bp.route("/api/balance", methods=["GET"])
@require_jwt
def get_balance():
    return jsonify(get_balance_response(g.user_id))
