"""Chat streaming via Backboard.

Implements the resumable SSE pattern the frontend expects:
  POST /api/agents/chat      -> start stream, return {streamId, conversationId}
  GET  /api/agents/chat/stream/:streamId -> SSE event stream
"""

import asyncio
import json
import logging
import os
import queue
import tempfile
import time
import uuid

from backboard import DocumentStatus
from backboard.exceptions import BackboardAPIError, BackboardValidationError
from flask import Blueprint, Response, g, jsonify, request

from api.config import settings
from api.middleware.jwt_auth import require_jwt
from api.routes.billing import get_user_plan
from api.routes.config_routes import FREE_TIER_PROVIDERS, _load_endpoint_config
from api.services.async_runner import iter_async, run_async
from api.services.backboard_service import (
    get_client,
    get_thread_messages,
    run_with_tool_loop,
    stream_message_proxy_compatible,
)
from api.services.balance_service import get_balance_response
from api.services.conversation_service import (
    _get_conversation_meta,
    _save_conversation_meta,
    get_or_create_thread,
    save_conversation_meta,
    save_fallback_notice,
    save_regen_graph,
)
from api.services.token_service import (
    check_token_limit,
    get_token_usage,
    record_token_usage,
)
from api.services.user_service import (
    find_user_by_id,
    get_user_assistant_id,
    get_user_config_assistant_id,
)

chat_bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)

_streams: dict[str, dict] = {}
FILE_META_TYPE = "file_meta"
FILE_POLL_INTERVAL_SEC = 2
FILE_POLL_MAX_ATTEMPTS = 150  # ~5 minutes per file if no phase limit
FILE_PROCESSING_PHASE_TIMEOUT_SEC = (
    90  # stop waiting on docs after this, proceed to reply
)
FILE_UPLOAD_TIMEOUT_SEC = 90  # max wait for Backboard upload_document_to_assistant
STREAM_IDLE_TIMEOUT_SEC = 45
STREAM_TOTAL_TIMEOUT_SEC = 180
LONG_MESSAGE_CHAR_THRESHOLD = settings.long_message_char_threshold

FALLBACK_MODEL_PAID = "openai/gpt-4.1"
FALLBACK_MODEL_FREE = "openrouter/openrouter/free"

_MODEL_FRIENDLY_NAMES: dict[str, str] = {
    "openai/gpt-4.1": "GPT-4.1",
    "openrouter/openrouter/free": "a free model",
    "openai/gpt-4o": "GPT-4o",
    "openai/gpt-4o-mini": "GPT-4o mini",
    "openai/o1": "o1",
    "openai/o3-mini": "o3 mini",
    "anthropic/claude-opus-4-5": "Claude Opus 4.5",
    "anthropic/claude-sonnet-4-5": "Claude Sonnet 4.5",
    "anthropic/claude-haiku-3-5": "Claude Haiku 3.5",
    "cohere/command-a-reasoning-08-2025": "Cohere Command A",
    "cohere/command-r-plus": "Cohere Command R+",
    "cohere/command-r": "Cohere Command R",
    "meta/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "google/gemini-2.0-flash": "Gemini 2.0 Flash",
    "google/gemini-1.5-pro": "Gemini 1.5 Pro",
}


def _friendly_model_name(model: str) -> str:
    """Return a short human-readable label for a model spec string."""
    if not model:
        return "The selected model"
    return _MODEL_FRIENDLY_NAMES.get(
        model, model.split("/")[-1].replace("-", " ").title()
    )


LONG_MESSAGE_STATUS_START = (
    "Big message detected. Indexing it in Backboard so I can read it cleanly."
)
LONG_MESSAGE_STATUS_INDEXING = "Indexing your message..."
LONG_MESSAGE_STATUS_DONE = "All set. Answering now."


def _log_stream_event(stream_id: str, stage: str, **extra):
    logger.warning(
        "[chat][stream:%s] %s %s", stream_id, stage, json.dumps(extra, default=str)
    )


def _extract_user_text(payload: dict) -> str:
    text = payload.get("text", "")
    if not text:
        messages = payload.get("messages", [])
        if messages:
            last = messages[-1] if isinstance(messages, list) else {}
            text = last.get("text", "") or last.get("content", "")
    return text


def _should_index_long_message(text: str) -> bool:
    return bool(text) and len(text) >= LONG_MESSAGE_CHAR_THRESHOLD


def _build_long_message_prompt(document_id: str) -> str:
    return (
        "The user's message was too long to send directly. "
        f"It has been uploaded to Backboard as document {document_id}. "
        "Read the document content and respond to the user's request."
    )


def _extract_requested_model(payload: dict) -> str:
    model = payload.get("model") or ""
    endpoint_option = payload.get("endpointOption", {})
    if not model and endpoint_option:
        model = endpoint_option.get("model", "") or endpoint_option.get(
            "modelLabel", ""
        )
    return model


def _is_free_tier_model(model_name: str) -> bool:
    if not model_name:
        return False

    normalized_model = model_name.lower().strip()

    cfg = _load_endpoint_config()
    model_pricing = cfg.get("modelPricing", {}) or {}
    pricing = model_pricing.get(model_name) or model_pricing.get(normalized_model) or {}
    if isinstance(pricing, dict):
        input_cost = float(pricing.get("inputCostPer1mTokens", 0) or 0)
        output_cost = float(pricing.get("outputCostPer1mTokens", 0) or 0)
        if input_cost <= 0 and output_cost <= 0:
            return True

    custom_endpoints = cfg.get("endpoints", {}).get("custom", [])
    for endpoint in custom_endpoints:
        selector_tiers = endpoint.get("selectorTiers", {}) or {}
        free_models = selector_tiers.get("free", []) or []
        for free_model in free_models:
            if (
                isinstance(free_model, str)
                and free_model.lower().strip() == normalized_model
            ):
                return True

    providers = {p.lower() for p in FREE_TIER_PROVIDERS}
    segments = normalized_model.split("/")
    return any(
        seg == provider or seg.startswith(f"{provider}-") or seg.startswith(provider)
        for provider in providers
        for seg in segments
    )


def _resolve_endpoint_for_model(model_name: str, fallback_endpoint: str) -> str:
    if not model_name:
        return fallback_endpoint

    normalized_model = model_name.lower().strip()
    cfg = _load_endpoint_config()
    custom_endpoints = cfg.get("endpoints", {}).get("custom", [])
    for endpoint_cfg in custom_endpoints:
        endpoint_name = endpoint_cfg.get("name", "") or fallback_endpoint
        raw_models = endpoint_cfg.get("models", {}).get("default", [])
        for raw_model in raw_models:
            candidate = (
                raw_model.get("name", "") if isinstance(raw_model, dict) else raw_model
            )
            if (
                isinstance(candidate, str)
                and candidate.lower().strip() == normalized_model
            ):
                return endpoint_name

    return fallback_endpoint


def _should_force_free_model_fallback(user_id: str, requested_model: str) -> bool:
    user = find_user_by_id(user_id)
    if not user:
        return False

    if get_user_plan(user) == "free":
        return False

    if _is_free_tier_model(requested_model):
        return False

    usage = get_token_usage(user_id)
    if usage["tokensRemaining"] > 0:
        return False

    balance = get_balance_response(user_id)
    if int(balance.get("tokenCredits", 0) or 0) > 0:
        return False

    if user.get("stripeMeteredItemId", ""):
        return False

    return True


def _is_tool_use_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "tool use" in lowered
        or "does not support tools" in lowered
        or "no endpoints found" in lowered
    )


async def _get_agent_bb_assistant_id(config_assistant_id: str, agent_id: str) -> str:
    """Look up the Backboard assistant ID for a user-created agent."""
    client = get_client()
    response = await client.get_memories(config_assistant_id)
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != "agent":
            continue
        try:
            agent_data = json.loads(m.content)
        except json.JSONDecodeError:
            continue
        if agent_data.get("id") == agent_id:
            return agent_data.get("bb_assistant_id", "")
    return ""


async def _get_folder_bb_assistant_id(config_assistant_id: str, folder_id: str) -> str:
    """Look up the Backboard assistant ID for a folder."""
    client = get_client()
    response = await client.get_memories(config_assistant_id)
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != "folder":
            continue
        try:
            folder_data = json.loads(m.content)
        except json.JSONDecodeError:
            continue
        if folder_data.get("folderId") == folder_id:
            return folder_data.get("bb_assistant_id", "")
    return ""


async def _list_file_metas(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    files = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != FILE_META_TYPE:
            continue
        try:
            f = json.loads(m.content)
            f["_memory_id"] = m.id
            files.append(f)
        except json.JSONDecodeError:
            continue
    return files


async def _process_pending_files_for_assistant(
    assistant_id: str,
    target_filepaths: set[str],
    events_queue: queue.Queue,
    response_message_id: str,
    conversation_id: str,
    user_message_id: str,
    chat_assistant_id: str = "",
):
    """Process file uploads and emit status events directly to the pre-stream queue."""
    phase_deadline = time.monotonic() + FILE_PROCESSING_PHASE_TIMEOUT_SEC

    def phase_timed_out() -> bool:
        return time.monotonic() >= phase_deadline

    def _status_event(text: str) -> dict:
        return {
            "type": "text",
            "text": {"value": text},
            "index": 0,
            "messageId": response_message_id,
            "conversationId": conversation_id,
            "userMessageId": user_message_id,
            "stream": True,
        }

    client = get_client()
    files = await _list_file_metas(assistant_id)
    pending_files = [
        f
        for f in files
        if f.get("status") != "indexed"
        and f.get("filepath")
        and f.get("filepath") in target_filepaths
    ]
    if not pending_files:
        logger.info(
            "[chat] file processing: no pending files for paths %s", target_filepaths
        )
        return

    logger.info(
        "[chat] file processing: starting, %d pending file(s), phase_timeout=%ds",
        len(pending_files),
        FILE_PROCESSING_PHASE_TIMEOUT_SEC,
    )

    for i, f in enumerate(pending_files, start=1):
        if phase_timed_out():
            logger.warning(
                "[chat] file processing: phase time limit reached, skipping remaining"
            )
            events_queue.put(
                _status_event(
                    "Document processing time limit reached. Continuing with reply."
                )
            )
            return
        filename = f.get("filename", "file")
        try:
            events_queue.put(
                _status_event(
                    f"Processing attached files ({i}/{len(pending_files)}): {filename}"
                )
            )

            filepath = f.get("filepath", "")
            if not filepath or not os.path.exists(filepath):
                logger.info(
                    "[chat] file processing: skip '%s' (no path or missing)", filename
                )
                continue

            logger.warning(
                "[chat] file processing: uploading '%s' to Backboard ...", filename
            )
            try:
                doc = await asyncio.wait_for(
                    client.upload_document_to_assistant(
                        assistant_id=chat_assistant_id or assistant_id,
                        file_path=filepath,
                    ),
                    timeout=FILE_UPLOAD_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[chat] file processing: upload timed out after %ds for '%s'",
                    FILE_UPLOAD_TIMEOUT_SEC,
                    filename,
                )
                events_queue.put(
                    _status_event(
                        f"Could not process {filename} (upload timed out). Continuing without it."
                    )
                )
                continue
            except Exception as e:
                logger.exception(
                    "Failed uploading pending file '%s' for assistant %s from %s",
                    filename,
                    assistant_id,
                    filepath,
                )
                events_queue.put(
                    _status_event(
                        f"Could not process {filename} ({e}). Continuing without it."
                    )
                )
                continue

            logger.info(
                "[chat] file processing: uploaded '%s', document_id=%s, polling for indexed ...",
                filename,
                doc.document_id,
            )

            for attempt in range(FILE_POLL_MAX_ATTEMPTS):
                if phase_timed_out():
                    logger.warning(
                        "[chat] file processing: phase time limit during poll for '%s'",
                        filename,
                    )
                    events_queue.put(
                        _status_event(
                            f"Still processing {filename}. Continuing with reply."
                        )
                    )
                    return
                try:
                    status = await client.get_document_status(doc.document_id)
                except BackboardAPIError as e:
                    logger.debug(
                        "[chat] file processing: poll attempt %d for '%s' got BackboardAPIError, retrying: %s",
                        attempt + 1,
                        filename,
                        e,
                    )
                    await asyncio.sleep(FILE_POLL_INTERVAL_SEC)
                    continue
                status_val = (
                    status.status.value
                    if hasattr(status.status, "value")
                    else str(status.status)
                )
                if (attempt + 1) % 15 == 0 or attempt == 0:
                    logger.info(
                        "[chat] file processing: poll attempt %d/%d for '%s': status=%s",
                        attempt + 1,
                        FILE_POLL_MAX_ATTEMPTS,
                        filename,
                        status_val,
                    )
                if status_val == DocumentStatus.INDEXED.value:
                    logger.info("[chat] file processing: '%s' indexed", filename)
                    break
                if status_val == DocumentStatus.FAILED.value:
                    msg = status.status_message or "Document processing failed"
                    logger.warning(
                        "[chat] file processing: '%s' failed: %s", filename, msg
                    )
                    events_queue.put(
                        _status_event(
                            f"Could not process {filename} ({msg}). Continuing without it."
                        )
                    )
                    doc = None
                    break
                await asyncio.sleep(FILE_POLL_INTERVAL_SEC)
            else:
                logger.warning(
                    "[chat] file processing: timed out waiting for '%s'", filename
                )
                events_queue.put(
                    _status_event(
                        f"Could not process {filename} (timed out). Continuing without it."
                    )
                )
                continue

            if doc is None:
                continue

            memory_id = f.get("_memory_id")
            if memory_id:
                updated = {
                    **{k: v for k, v in f.items() if not k.startswith("_")},
                    "status": "indexed",
                    "document_id": str(doc.document_id),
                }
                try:
                    await client.update_memory(
                        assistant_id=assistant_id,
                        memory_id=memory_id,
                        content=json.dumps(updated),
                        metadata={
                            "type": FILE_META_TYPE,
                            "fileId": updated.get("file_id"),
                            "filename": filename,
                        },
                    )
                except Exception:
                    logger.exception(
                        "Failed to update file memory for '%s' (%s)",
                        filename,
                        memory_id,
                    )
        except Exception:
            logger.exception(
                "Unexpected error while processing pending file '%s'", filename
            )
            events_queue.put(
                _status_event(f"Could not process {filename}. Continuing without it.")
            )

    logger.warning("[chat] file processing: done, calling add_message next")


async def _index_long_message_for_assistant(
    assistant_id: str,
    content: str,
    events_queue: queue.Queue,
    response_message_id: str,
    conversation_id: str,
    user_message_id: str,
) -> str:
    """Upload a long message as a document and wait for it to index."""

    def _status_event(text: str) -> dict:
        return {
            "type": "text",
            "text": {"value": text},
            "index": 0,
            "messageId": response_message_id,
            "conversationId": conversation_id,
            "userMessageId": user_message_id,
            "stream": True,
        }

    client = get_client()
    events_queue.put(_status_event(LONG_MESSAGE_STATUS_START))

    filepath = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as handle:
            handle.write(content)
            filepath = handle.name

        events_queue.put(_status_event(LONG_MESSAGE_STATUS_INDEXING))
        doc = await asyncio.wait_for(
            client.upload_document_to_assistant(
                assistant_id=assistant_id,
                file_path=filepath,
            ),
            timeout=FILE_UPLOAD_TIMEOUT_SEC,
        )
    finally:
        if filepath:
            try:
                os.unlink(filepath)
            except Exception:
                logger.exception(
                    "[chat] long message: failed to remove temp file %s", filepath
                )

    for attempt in range(FILE_POLL_MAX_ATTEMPTS):
        status = await client.get_document_status(doc.document_id)
        status_val = (
            status.status.value
            if hasattr(status.status, "value")
            else str(status.status)
        )
        if (attempt + 1) % 15 == 0 or attempt == 0:
            logger.info(
                "[chat] long message: poll %d/%d status=%s",
                attempt + 1,
                FILE_POLL_MAX_ATTEMPTS,
                status_val,
            )
        if status_val == DocumentStatus.INDEXED.value:
            events_queue.put(_status_event(LONG_MESSAGE_STATUS_DONE))
            return str(doc.document_id)
        if status_val == DocumentStatus.FAILED.value:
            msg = status.status_message or "Document processing failed"
            raise RuntimeError(msg)
        await asyncio.sleep(FILE_POLL_INTERVAL_SEC)

    raise RuntimeError("Timed out waiting for message indexing")


def _prepare_stream(stream_id: str, user_id: str, payload: dict) -> dict:
    """Resolve IDs and prepare the stream context (runs on request thread).

    Returns a dict with all the context needed for generate() to pull
    directly from the Backboard stream.  Also enqueues any file-processing
    status events into a small pre-stream queue that generate() drains first.
    """
    assistant_id = get_user_assistant_id(user_id)
    config_assistant_id = get_user_config_assistant_id(user_id)
    conversation_id = payload.get("conversationId")

    agent_id = payload.get("agent_id", "")
    ephemeral_agent = payload.get("ephemeralAgent") or {}
    agent_bb_assistant_id = ""

    if isinstance(ephemeral_agent, dict) and ephemeral_agent.get("bb_assistant_id"):
        agent_bb_assistant_id = ephemeral_agent["bb_assistant_id"]
        logger.warning(
            "[chat] using ephemeral agent bb_assistant_id=%s, agent=%s",
            agent_bb_assistant_id,
            ephemeral_agent.get("name", ""),
        )
    elif agent_id and agent_id.startswith("agent_"):
        try:
            agent_bb_assistant_id = run_async(
                _get_agent_bb_assistant_id(config_assistant_id, agent_id)
            )
            if agent_bb_assistant_id:
                logger.warning(
                    "[chat] resolved agent_id=%s -> bb_assistant_id=%s",
                    agent_id,
                    agent_bb_assistant_id,
                )
            else:
                logger.warning(
                    "[chat] agent_id=%s has no bb_assistant_id, falling back to default",
                    agent_id,
                )
        except Exception:
            logger.exception(
                "Failed to resolve bb_assistant_id for agent_id=%s", agent_id
            )

    folder_id = payload.get("folderId", "") if not agent_bb_assistant_id else ""
    folder_bb_assistant_id = ""
    if not agent_bb_assistant_id and folder_id:
        try:
            folder_bb_assistant_id = run_async(
                _get_folder_bb_assistant_id(config_assistant_id, folder_id)
            )
            if folder_bb_assistant_id:
                logger.warning(
                    "[chat] resolved folder_id=%s -> bb_assistant_id=%s",
                    folder_id,
                    folder_bb_assistant_id,
                )
            else:
                logger.warning(
                    "[chat] folder_id=%s has no bb_assistant_id, falling back to default",
                    folder_id,
                )
        except Exception:
            logger.exception(
                "Failed to resolve bb_assistant_id for folder_id=%s", folder_id
            )

    thread_owner_id = agent_bb_assistant_id or folder_bb_assistant_id or assistant_id
    thread_id, conversation_id, is_new = get_or_create_thread(
        thread_owner_id, conversation_id
    )

    # For new folder conversations, eagerly write hidden conversation_meta so the
    # conversation never leaks into the main list even during the first stream.
    if is_new and folder_id and not agent_bb_assistant_id:
        try:
            run_async(
                _save_conversation_meta(
                    assistant_id,
                    conversation_id,
                    {"folderId": folder_id, "hidden": True, "title": "New Chat"},
                )
            )
        except Exception:
            logger.exception(
                "[chat] stream: failed to pre-save folder conversation meta"
            )

    user_text = _extract_user_text(payload)
    model_text = user_text
    should_index_long_message = _should_index_long_message(user_text)
    model = payload.get("model") or ""
    endpoint = payload.get("endpoint") or payload.get("endpointType") or "bedrock"
    endpoint_option = payload.get("endpointOption", {})
    if not model and endpoint_option:
        model = endpoint_option.get("model", "") or endpoint_option.get(
            "modelLabel", ""
        )

    is_temporary_chat = bool(payload.get("isTemporary"))
    mem_toggle = (
        "Off"
        if is_temporary_chat
        else (
            ephemeral_agent.get("memory", "Auto")
            if isinstance(ephemeral_agent, dict)
            else "Auto"
        )
    )
    bb_memory = {"Auto": "Auto", "Readonly": "Readonly", "On": "On", "Off": "off"}.get(
        mem_toggle, "off"
    )
    requested_web_search = (
        "Auto"
        if isinstance(ephemeral_agent, dict)
        and ephemeral_agent.get("web_search") is True
        else None
    )

    pre_queue = queue.Queue()

    requested_files = payload.get("files", [])
    requested_paths = {
        f.get("filepath", "")
        for f in requested_files
        if isinstance(f, dict) and f.get("filepath")
    }
    if requested_paths:
        logger.info(
            "[chat] stream: processing pending files (paths=%s)", requested_paths
        )
        run_async(
            _process_pending_files_for_assistant(
                assistant_id=config_assistant_id,
                target_filepaths=requested_paths,
                events_queue=pre_queue,
                response_message_id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_message_id=str(uuid.uuid4()),
                chat_assistant_id=assistant_id,
            )
        )

    # Resolve fallback model by plan (opt-out, not opt-in).
    # Free tier falls back to a free OpenRouter model; paid tiers fall back to GPT-4.1.
    # Frontend sends ephemeralAgent.fallback_model = False to disable entirely.
    user_for_fallback = find_user_by_id(user_id)
    user_plan = get_user_plan(user_for_fallback)
    fallback_model: str | None = (
        FALLBACK_MODEL_PAID if user_plan != "free" else FALLBACK_MODEL_FREE
    )
    if (
        isinstance(ephemeral_agent, dict)
        and ephemeral_agent.get("fallback_model") is False
    ):
        fallback_model = None

    forced_fallback_prefix = ""
    if model and _should_force_free_model_fallback(user_id, model):
        forced_fallback_prefix = (
            f"*{_friendly_model_name(model)} exceeded your included paid-plan usage, "
            f"so I used {_friendly_model_name(FALLBACK_MODEL_FREE)} instead because you have no credits or metered billing configured.*\n\n"
        )
        logger.warning(
            "[chat] forcing free-model fallback for user_id=%s requested_model=%s fallback_model=%s",
            user_id,
            model,
            FALLBACK_MODEL_FREE,
        )
        model = FALLBACK_MODEL_FREE
        endpoint = _resolve_endpoint_for_model(model, endpoint)

    # Load MCP server configs if any are enabled for this conversation.
    mcp_server_map: dict = {}
    if isinstance(ephemeral_agent, dict):
        mcp_enabled = ephemeral_agent.get("mcp", {}) or {}
        if mcp_enabled:
            from api.routes.misc import _list_mcp_servers

            all_servers = run_async(_list_mcp_servers(config_assistant_id))
            for s in all_servers:
                sname = s.get("serverName", "")
                # frontend sends {serverName: true} or {serverName: MCPServerRecord}
                if sname and sname in mcp_enabled:
                    mcp_server_map[sname] = s

    return {
        "assistant_id": assistant_id,
        "config_assistant_id": config_assistant_id,
        "thread_id": thread_id,
        "conversation_id": conversation_id,
        "folder_id": folder_id,
        "user_text": user_text,
        "model_text": model_text,
        "should_index_long_message": should_index_long_message,
        "model": model,
        "endpoint": endpoint,
        "bb_memory": bb_memory,
        "requested_web_search": requested_web_search,
        "pre_queue": pre_queue,
        "mcp_server_map": mcp_server_map,
        "fallback_model": fallback_model,
        "forced_fallback_prefix": forced_fallback_prefix,
    }


def _open_backboard_stream(
    ctx: dict, web_search_mode: str | None, model_override: str | None = None
):
    """Open the Backboard async stream and return a sync iterator via iter_async."""

    async def _open():
        return await stream_message_proxy_compatible(
            thread_id=ctx["thread_id"],
            content=ctx["model_text"],
            model=model_override or ctx["model"] or None,
            memory=ctx["bb_memory"],
            web_search=web_search_mode,
        )

    async_iter = run_async(_open())
    return iter_async(async_iter, idle_timeout=STREAM_IDLE_TIMEOUT_SEC)


@chat_bp.route("/api/agents/chat", methods=["POST"])
@chat_bp.route("/api/agents/chat/<endpoint_name>", methods=["POST"])
@require_jwt
def start_chat(endpoint_name=None):
    payload = request.get_json() or {}
    stream_id = str(uuid.uuid4())
    conversation_id = payload.get("conversationId", "")
    logger.warning(
        "[chat] start_chat stream_id=%s endpoint_name=%s conversation_id=%s model=%s endpoint=%s",
        stream_id,
        endpoint_name,
        conversation_id,
        payload.get("model"),
        payload.get("endpoint") or payload.get("endpointType"),
    )

    requested_model = _extract_requested_model(payload)
    user = find_user_by_id(g.user_id)
    plan = get_user_plan(user)
    force_free_model_fallback = (
        plan != "free"
        and requested_model
        and _should_force_free_model_fallback(g.user_id, requested_model)
    )
    limit_error = (
        None
        if force_free_model_fallback
        else check_token_limit(g.user_id, requested_model)
    )
    if limit_error:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        user_text = _extract_user_text(payload)
        user_message_id = str(uuid.uuid4())
        error_message_id = str(uuid.uuid4())
        endpoint = payload.get("endpoint") or payload.get("endpointType") or "Nash"
        model = payload.get("model") or ""
        parent_msg_id = payload.get(
            "parentMessageId", "00000000-0000-0000-0000-000000000000"
        )

        user_message = {
            "messageId": user_message_id,
            "conversationId": conversation_id,
            "parentMessageId": parent_msg_id,
            "text": user_text,
            "sender": "User",
            "isCreatedByUser": True,
            "createdAt": now,
            "error": False,
        }

        error_text = (
            "**You\u2019ve reached your token limit for this month.**\n\n"
            "Upgrade your plan to keep chatting:\n"
            "- **Plus** \u2014 500,000 tokens/month + all models\n"
            "- **Unlimited** \u2014 3,000,000 tokens/month + all models\n\n"
            "Click your name in the bottom-left corner, then open **Settings \u2192 Billing** to upgrade."
        )

        _q: queue.Queue = queue.Queue()
        _q.put({"created": True, "message": user_message})
        _q.put(
            {
                "final": True,
                "requestMessage": user_message,
                "responseMessage": {
                    "messageId": error_message_id,
                    "conversationId": conversation_id,
                    "parentMessageId": user_message_id,
                    "text": error_text,
                    "sender": "Nash",
                    "isCreatedByUser": False,
                    "model": model,
                    "endpoint": endpoint,
                    "createdAt": now,
                    "error": True,
                    "unfinished": False,
                    "content": [{"type": "text", "text": {"value": error_text}}],
                },
                "conversation": {
                    "conversationId": conversation_id,
                    "title": None,
                    "endpoint": endpoint,
                    "model": model,
                    "createdAt": now,
                    "updatedAt": now,
                },
            }
        )
        _streams[stream_id] = {
            "events": _q,
            "done": True,
            "conversationId": conversation_id,
            "userId": g.user_id,
        }
        _log_stream_event(stream_id, "limit_error_stream_created")
        return jsonify(
            {
                "streamId": stream_id,
                "conversationId": conversation_id,
                "status": "started",
            }
        )

    if plan == "free" and requested_model and not _is_free_tier_model(requested_model):
        return (
            jsonify(
                {
                    "error": "This model requires a paid plan. Select a free model or upgrade in Settings -> Billing.",
                    "code": "premium_model_requires_upgrade",
                }
            ),
            403,
        )

    # Store just enough for the SSE endpoint to resolve the stream context.
    _streams[stream_id] = {
        "userId": g.user_id,
        "payload": payload,
        "conversationId": conversation_id,
        "done": False,
    }
    _log_stream_event(stream_id, "stream_created")

    return jsonify(
        {
            "streamId": stream_id,
            "conversationId": conversation_id,
            "status": "started",
        }
    )


@chat_bp.route("/api/agents/chat/stream/<stream_id>", methods=["GET"])
@require_jwt
def stream_chat(stream_id):
    is_resume = request.args.get("resume") == "true"
    stream_state = _streams.get(stream_id)
    _log_stream_event(stream_id, "sse_connect", isResume=is_resume)

    if not stream_state:
        if is_resume:

            def completed():
                yield f"data: {json.dumps({'final': True, 'completed': True})}\n\n"

            return Response(
                completed(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        return jsonify({"error": "Stream not found"}), 404

    # Token-limit streams already have a pre-filled queue; drain it directly.
    if stream_state.get("done") and "events" in stream_state:

        def drain_queue():
            q: queue.Queue = stream_state["events"]
            while not q.empty():
                event = q.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"
            _streams.pop(stream_id, None)

        return Response(
            drain_queue(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Guard: if generate() is already running (or finished) for this stream,
    # a resume connection must not re-run the pipeline.
    if stream_state.get("generating"):
        _log_stream_event(stream_id, "resume_already_generating", isResume=is_resume)

        def already_done():
            yield f"data: {json.dumps({'final': True, 'completed': True})}\n\n"

        return Response(
            already_done(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    stream_state["generating"] = True

    def generate():
        """Pull-based SSE generator — no queue, no background thread.

        Opens the Backboard stream and yields each chunk as an SSE event
        directly, mirroring the Backboard API's own streaming approach.
        """
        payload = stream_state.pop("payload", {})
        user_id = stream_state["userId"]
        full_text = ""
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        conversation_id = stream_state.get("conversationId", "")
        fallback_succeeded = False

        try:
            ctx = _prepare_stream(stream_id, user_id, payload)
            persisted_fallback_prefix = ctx.get("forced_fallback_prefix", "")
        except Exception:
            logger.exception(
                "[chat] stream: prepare failed for stream_id=%s", stream_id
            )
            yield f"data: {json.dumps({'final': True, 'conversation': {'conversationId': conversation_id}, 'requestMessage': None, 'responseMessage': {'text': 'I ran into an error starting your response. Please try again.', 'error': True}})}\n\n"
            _streams.pop(stream_id, None)
            return

        conversation_id = ctx["conversation_id"]
        stream_state["conversationId"] = conversation_id
        thread_id = ctx["thread_id"]
        model = ctx["model"]
        endpoint = ctx["endpoint"]

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        user_message_id = str(uuid.uuid4())
        response_message_id = str(uuid.uuid4())
        parent_message_id = payload.get(
            "parentMessageId", "00000000-0000-0000-0000-000000000000"
        )
        override_parent_message_id = payload.get("overrideParentMessageId")
        is_regenerate = payload.get("isRegenerate", False)

        user_message = {
            "messageId": user_message_id,
            "conversationId": conversation_id,
            "parentMessageId": parent_message_id,
            "text": ctx["user_text"],
            "sender": "User",
            "isCreatedByUser": True,
            "createdAt": now,
            "error": False,
        }

        yield f"data: {json.dumps({'created': True, 'message': user_message, 'responseMessageId': response_message_id})}\n\n"

        # Index long messages before streaming (and before draining status events).
        if ctx.get("should_index_long_message"):
            try:
                doc_id = run_async(
                    _index_long_message_for_assistant(
                        assistant_id=ctx["assistant_id"],
                        content=ctx["user_text"],
                        events_queue=ctx["pre_queue"],
                        response_message_id=response_message_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message_id,
                    )
                )
                ctx["model_text"] = _build_long_message_prompt(doc_id)
            except Exception as e:
                logger.exception(
                    "[chat] long message: indexing failed for conversation %s",
                    conversation_id,
                )
                full_text = f"Sorry, I could not index that long message. {e}"

        # Drain any file-processing or long-message status events first.
        pre_q: queue.Queue = ctx["pre_queue"]
        while not pre_q.empty():
            yield f"data: {json.dumps(pre_q.get_nowait())}\n\n"

        mcp_server_map = ctx.get("mcp_server_map", {})

        logger.warning(
            "[chat] stream: opening Backboard stream (thread_id=%s, model=%r, memory=%s, web_search=%r, mcp_servers=%s)",
            thread_id,
            model,
            ctx["bb_memory"],
            ctx["requested_web_search"],
            list(mcp_server_map.keys()),
        )

        if full_text:
            total_tokens = (len(ctx["model_text"]) + len(full_text)) // 4 + 1
        elif mcp_server_map:
            # MCP path: use non-streaming tool loop, then fake-stream the result
            try:
                final_answer = run_async(
                    run_with_tool_loop(
                        assistant_id=ctx["assistant_id"],
                        thread_id=thread_id,
                        content=ctx["model_text"],
                        mcp_server_map=mcp_server_map,
                    ),
                    timeout=120,
                )
                full_text = final_answer or ""
                total_tokens = (len(ctx["user_text"]) + len(full_text)) // 4 + 1
                # Emit a single streaming chunk so the UI renders progressively
                yield f"data: {json.dumps({'type': 'text', 'text': {'value': full_text}, 'index': 0, 'messageId': response_message_id, 'conversationId': conversation_id, 'userMessageId': user_message_id, 'thread_id': thread_id, 'stream': True})}\n\n"
            except Exception as e:
                logger.exception(
                    "[chat] stream: MCP tool loop failed for conversation %s",
                    conversation_id,
                )
                full_text = f"[Error: {e}]"
        else:

            def _consume(web_search_mode, model_override: str | None = None):
                nonlocal full_text, total_tokens, input_tokens, output_tokens
                stream_started = time.monotonic()
                chunk_count = 0
                for chunk in _open_backboard_stream(
                    ctx, web_search_mode, model_override=model_override
                ):
                    if time.monotonic() - stream_started >= STREAM_TOTAL_TIMEOUT_SEC:
                        logger.warning(
                            "[chat] stream: total timeout after %ss",
                            STREAM_TOTAL_TIMEOUT_SEC,
                        )
                        full_text += "\n\n[Error: response timed out]"
                        return
                    chunk_type = chunk.get("type", "")
                    if chunk_type == "content_streaming":
                        content = chunk.get("content", "")
                        full_text += content
                        chunk_count += 1
                        if chunk_count <= 3:
                            logger.warning(
                                "[chat] stream: chunk %d len=%d",
                                chunk_count,
                                len(content),
                            )
                        rendered_text = (
                            persisted_fallback_prefix + full_text
                            if persisted_fallback_prefix
                            else full_text
                        )
                        yield {
                            "type": "text",
                            "text": {"value": rendered_text},
                            "index": 0,
                            "messageId": response_message_id,
                            "conversationId": conversation_id,
                            "userMessageId": user_message_id,
                            "thread_id": thread_id,
                            "stream": True,
                        }
                    elif chunk_type in ("run_ended", "run_completed"):
                        input_tokens = int(chunk.get("input_tokens", 0) or 0)
                        output_tokens = int(chunk.get("output_tokens", 0) or 0)
                        total_tokens = int(chunk.get("total_tokens", 0) or 0)
                        logger.warning(
                            "[chat] stream: %s, input_tokens=%d, output_tokens=%d, total_tokens=%d",
                            chunk_type,
                            input_tokens,
                            output_tokens,
                            total_tokens,
                        )
                        return
                    elif chunk_type in ("error", "run_failed"):
                        error_msg = chunk.get("error") or chunk.get(
                            "message", "Unknown error"
                        )
                        raise BackboardAPIError(error_msg)

            try:
                try:
                    for event in _consume(ctx["requested_web_search"]):
                        yield f"data: {json.dumps(event)}\n\n"
                except BackboardAPIError as e:
                    if (
                        ctx["requested_web_search"]
                        and not full_text
                        and _is_tool_use_error(str(e))
                    ):
                        logger.warning(
                            "[chat] stream: retrying without web_search (model=%r)",
                            model,
                        )
                        for event in _consume(None):
                            yield f"data: {json.dumps(event)}\n\n"
                    elif (
                        ctx.get("fallback_model")
                        and ctx["model"] != ctx["fallback_model"]
                    ):
                        # Primary model failed — attempt tier-appropriate fallback.
                        original_model = ctx["model"]
                        chosen_fallback: str = ctx["fallback_model"]
                        logger.warning(
                            "[chat] stream: primary model %r failed (%s), falling back to %s",
                            original_model,
                            e,
                            chosen_fallback,
                        )
                        fallback_prefix = (
                            f"*{_friendly_model_name(original_model)} wasn't available, "
                            f"so I used {_friendly_model_name(chosen_fallback)} instead.*\n\n"
                        )
                        persisted_fallback_prefix = fallback_prefix
                        full_text = ""
                        try:
                            for event in _consume(None, model_override=chosen_fallback):
                                # Prepend the notice to every streamed chunk so the UI
                                # always shows the full text including the header.
                                event_with_prefix = dict(event)
                                event_with_prefix["text"] = {
                                    "value": fallback_prefix + full_text
                                }
                                yield f"data: {json.dumps(event_with_prefix)}\n\n"
                            # full_text was accumulated by _consume; prepend the notice.
                            full_text = fallback_prefix + full_text
                            model = chosen_fallback
                            endpoint = _resolve_endpoint_for_model(
                                chosen_fallback, endpoint
                            )
                            ctx["model"] = chosen_fallback
                            ctx["endpoint"] = endpoint
                            fallback_succeeded = True
                        except Exception:
                            logger.exception(
                                "[chat] stream: fallback model %s also failed for conversation %s",
                                chosen_fallback,
                                conversation_id,
                            )
                            full_text = "I ran into an error generating a response and the fallback model also failed. Please try again."
                    else:
                        logger.warning(
                            "[chat] stream: Backboard API error (fallback model)=%s", e
                        )
                        full_text = "I ran into an error generating a response. Please try again."
            except Exception as e:
                logger.exception(
                    "[chat] stream: failed for conversation %s", conversation_id
                )
                full_text += "\n\nI ran into an unexpected error. Please try again."

        if total_tokens == 0:
            total_tokens = (len(ctx["user_text"]) + len(full_text)) // 4 + 1
            if input_tokens == 0 and output_tokens == 0:
                input_tokens = max(1, len(ctx["user_text"]) // 4)
                output_tokens = max(1, total_tokens - input_tokens)

        if total_tokens > 0:
            record_token_usage(
                user_id,
                total_tokens,
                model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        final_text = (
            persisted_fallback_prefix + full_text
            if persisted_fallback_prefix
            else full_text
        )

        response_message = {
            "messageId": response_message_id,
            "conversationId": conversation_id,
            "parentMessageId": (override_parent_message_id or parent_message_id)
            if is_regenerate
            else user_message_id,
            "text": final_text,
            "sender": "Nash",
            "isCreatedByUser": False,
            "model": model,
            "endpoint": endpoint,
            "createdAt": now,
            "error": False,
            "unfinished": False,
            "content": [{"type": "text", "text": {"value": final_text}}],
        }

        final_event = {
            "final": True,
            "requestMessage": user_message,
            "responseMessage": response_message,
            "conversation": {
                "conversationId": conversation_id,
                "title": None,
                "endpoint": endpoint,
                "model": model,
                "createdAt": now,
                "updatedAt": now,
            },
        }

        title = full_text[:60].replace("\n", " ").strip()
        if not title:
            title = "New Chat"
        elif len(full_text) > 60:
            title += "..."

        existing_meta = run_async(
            _get_conversation_meta(ctx["assistant_id"], conversation_id)
        )
        existing_title = existing_meta.get("title", "")
        should_set_title = not existing_title or existing_title == "New Chat"

        if is_regenerate:
            try:
                bb_msgs = run_async(get_thread_messages(thread_id))
                # Thread ends with: [..., uN, aN, uN_regen, aN_regen]
                # We want aN_regen to share uN as its parent (same as aN), and uN_regen to be skipped.
                if (
                    len(bb_msgs) >= 4
                    and bb_msgs[-1].role == "assistant"
                    and bb_msgs[-2].role == "user"
                ):
                    regen_ai_id = bb_msgs[-1].message_id
                    regen_user_id = bb_msgs[-2].message_id
                    original_user_id = bb_msgs[-4].message_id
                    save_regen_graph(
                        ctx["assistant_id"],
                        conversation_id,
                        {
                            regen_ai_id: original_user_id,
                            regen_user_id: "SKIP",
                        },
                    )
                    logger.warning(
                        "[chat] regen_graph saved regen_ai=%s -> original_user=%s",
                        regen_ai_id,
                        original_user_id,
                    )
            except Exception:
                logger.exception("[chat] stream: failed to save regen graph")
        elif fallback_succeeded:
            try:
                bb_msgs = run_async(get_thread_messages(thread_id))
                # Fallback retry appends a second user/assistant pair to the same thread:
                # [..., user_primary, assistant_error, user_fallback, assistant_fallback]
                # Hide the failed attempt and duplicate retry user on reload, and attach the
                # successful fallback assistant to the original user message.
                if (
                    len(bb_msgs) >= 4
                    and bb_msgs[-1].role == "assistant"
                    and bb_msgs[-2].role == "user"
                    and bb_msgs[-3].role == "assistant"
                    and bb_msgs[-4].role == "user"
                ):
                    fallback_ai_id = bb_msgs[-1].message_id
                    fallback_user_id = bb_msgs[-2].message_id
                    failed_ai_id = bb_msgs[-3].message_id
                    original_user_id = bb_msgs[-4].message_id
                    save_regen_graph(
                        ctx["assistant_id"],
                        conversation_id,
                        {
                            fallback_ai_id: original_user_id,
                            fallback_user_id: "SKIP",
                            failed_ai_id: "SKIP",
                        },
                    )
                    save_fallback_notice(
                        ctx["assistant_id"],
                        conversation_id,
                        {
                            str(fallback_ai_id): persisted_fallback_prefix,
                        },
                    )
                    logger.warning(
                        "[chat] fallback_graph saved fallback_ai=%s -> original_user=%s, skipped failed_ai=%s and retry_user=%s",
                        fallback_ai_id,
                        original_user_id,
                        failed_ai_id,
                        fallback_user_id,
                    )
            except Exception:
                logger.exception("[chat] stream: failed to save fallback graph")

        try:
            meta = {"endpoint": endpoint, "model": model}
            if should_set_title:
                meta["title"] = title
            if ctx.get("folder_id"):
                meta["folderId"] = ctx["folder_id"]
            run_async(
                _save_conversation_meta(ctx["assistant_id"], conversation_id, meta)
            )
        except Exception:
            logger.exception("[chat] stream: failed to save conversation meta")

        # Remove from _streams BEFORE yielding the final event so the
        # status endpoint returns active=false before the client's
        # useResumeOnLoad can fire.
        _streams.pop(stream_id, None)
        _log_stream_event(
            stream_id,
            "stream_complete",
            totalTokens=total_tokens,
            responseLength=len(full_text),
        )

        yield f"data: {json.dumps(final_event)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/api/agents/chat/active", methods=["GET"])
@require_jwt
def active_jobs():
    active_ids = [
        sid
        for sid, s in _streams.items()
        if s.get("userId") == g.user_id and not s.get("done") and s.get("generating")
    ]
    logger.warning("[chat] active_jobs user_id=%s active_ids=%s", g.user_id, active_ids)
    return jsonify({"activeJobIds": active_ids})


@chat_bp.route("/api/agents/chat/status/<conversation_id>", methods=["GET"])
@require_jwt
def chat_status(conversation_id):
    for sid, s in _streams.items():
        if s.get("conversationId") == conversation_id and not s.get("done"):
            _log_stream_event(
                sid, "status_active_hit", requestedConversationId=conversation_id
            )
            return jsonify({"active": True, "streamId": sid})
    logger.warning("[chat] status_inactive requestedConversationId=%s", conversation_id)
    return jsonify({"active": False})


@chat_bp.route("/api/agents/chat/abort", methods=["POST"])
@require_jwt
def abort_chat():
    data = request.get_json() or {}
    stream_id = data.get("streamId")
    if stream_id and stream_id in _streams:
        _streams[stream_id]["done"] = True
        _log_stream_event(stream_id, "abort_marked_done")
    return jsonify({"message": "Aborted"})


@chat_bp.route("/api/agents/tools/calls", methods=["GET"])
@require_jwt
def tool_calls():
    return jsonify([])
