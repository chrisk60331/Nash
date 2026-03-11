"""Chat streaming via Backboard.

Implements the resumable SSE pattern the frontend expects:
  POST /api/agents/chat      -> start stream, return {streamId, conversationId}
  GET  /api/agents/chat/stream/:streamId -> SSE event stream
"""
import uuid
import json
import queue
import time
import os
import asyncio
import logging

from flask import Blueprint, request, jsonify, g, Response

from backboard import DocumentStatus
from backboard.exceptions import BackboardAPIError, BackboardValidationError
from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client, stream_message_proxy_compatible, run_with_tool_loop, get_thread_messages
from api.services.async_runner import run_async, iter_async
from api.services.user_service import get_user_assistant_id, get_user_config_assistant_id, find_user_by_id
from api.services.conversation_service import (
    get_or_create_thread,
    save_conversation_meta,
    _save_conversation_meta,
    save_regen_graph,
)
from api.services.token_service import check_token_limit, record_token_usage
from api.routes.billing import get_user_plan
from api.routes.config_routes import FREE_TIER_PROVIDERS

chat_bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)

_streams: dict[str, dict] = {}
FILE_META_TYPE = "file_meta"
FILE_POLL_INTERVAL_SEC = 2
FILE_POLL_MAX_ATTEMPTS = 150  # ~5 minutes per file if no phase limit
FILE_PROCESSING_PHASE_TIMEOUT_SEC = 90  # stop waiting on docs after this, proceed to reply
FILE_UPLOAD_TIMEOUT_SEC = 90  # max wait for Backboard upload_document_to_assistant
STREAM_IDLE_TIMEOUT_SEC = 45
STREAM_TOTAL_TIMEOUT_SEC = 180


def _log_stream_event(stream_id: str, stage: str, **extra):
    logger.warning("[chat][stream:%s] %s %s", stream_id, stage, json.dumps(extra, default=str))


def _extract_user_text(payload: dict) -> str:
    text = payload.get("text", "")
    if not text:
        messages = payload.get("messages", [])
        if messages:
            last = messages[-1] if isinstance(messages, list) else {}
            text = last.get("text", "") or last.get("content", "")
    return text


def _extract_requested_model(payload: dict) -> str:
    model = payload.get("model") or ""
    endpoint_option = payload.get("endpointOption", {})
    if not model and endpoint_option:
        model = endpoint_option.get("model", "") or endpoint_option.get("modelLabel", "")
    return model


def _is_free_tier_model(model_name: str) -> bool:
    if not model_name:
        return False

    providers = {p.lower() for p in FREE_TIER_PROVIDERS}
    segments = model_name.lower().split("/")
    return any(
        seg == provider or seg.startswith(f"{provider}-") or seg.startswith(provider)
        for provider in providers
        for seg in segments
    )


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
        logger.info("[chat] file processing: no pending files for paths %s", target_filepaths)
        return

    logger.info("[chat] file processing: starting, %d pending file(s), phase_timeout=%ds", len(pending_files), FILE_PROCESSING_PHASE_TIMEOUT_SEC)

    for i, f in enumerate(pending_files, start=1):
        if phase_timed_out():
            logger.warning("[chat] file processing: phase time limit reached, skipping remaining")
            events_queue.put(_status_event("Document processing time limit reached. Continuing with reply."))
            return
        filename = f.get("filename", "file")
        try:
            events_queue.put(_status_event(f"Processing attached files ({i}/{len(pending_files)}): {filename}"))

            filepath = f.get("filepath", "")
            if not filepath or not os.path.exists(filepath):
                logger.info("[chat] file processing: skip '%s' (no path or missing)", filename)
                continue

            logger.warning("[chat] file processing: uploading '%s' to Backboard ...", filename)
            try:
                doc = await asyncio.wait_for(
                    client.upload_document_to_assistant(
                        assistant_id=chat_assistant_id or assistant_id,
                        file_path=filepath,
                    ),
                    timeout=FILE_UPLOAD_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.warning("[chat] file processing: upload timed out after %ds for '%s'", FILE_UPLOAD_TIMEOUT_SEC, filename)
                events_queue.put(_status_event(f"Could not process {filename} (upload timed out). Continuing without it."))
                continue
            except Exception as e:
                logger.exception("Failed uploading pending file '%s' for assistant %s from %s", filename, assistant_id, filepath)
                events_queue.put(_status_event(f"Could not process {filename} ({e}). Continuing without it."))
                continue

            logger.info("[chat] file processing: uploaded '%s', document_id=%s, polling for indexed ...", filename, doc.document_id)

            for attempt in range(FILE_POLL_MAX_ATTEMPTS):
                if phase_timed_out():
                    logger.warning("[chat] file processing: phase time limit during poll for '%s'", filename)
                    events_queue.put(_status_event(f"Still processing {filename}. Continuing with reply."))
                    return
                try:
                    status = await client.get_document_status(doc.document_id)
                except BackboardAPIError as e:
                    logger.debug("[chat] file processing: poll attempt %d for '%s' got BackboardAPIError, retrying: %s", attempt + 1, filename, e)
                    await asyncio.sleep(FILE_POLL_INTERVAL_SEC)
                    continue
                status_val = status.status.value if hasattr(status.status, "value") else str(status.status)
                if (attempt + 1) % 15 == 0 or attempt == 0:
                    logger.info("[chat] file processing: poll attempt %d/%d for '%s': status=%s", attempt + 1, FILE_POLL_MAX_ATTEMPTS, filename, status_val)
                if status_val == DocumentStatus.INDEXED.value:
                    logger.info("[chat] file processing: '%s' indexed", filename)
                    break
                if status_val == DocumentStatus.FAILED.value:
                    msg = status.status_message or "Document processing failed"
                    logger.warning("[chat] file processing: '%s' failed: %s", filename, msg)
                    events_queue.put(_status_event(f"Could not process {filename} ({msg}). Continuing without it."))
                    doc = None
                    break
                await asyncio.sleep(FILE_POLL_INTERVAL_SEC)
            else:
                logger.warning("[chat] file processing: timed out waiting for '%s'", filename)
                events_queue.put(_status_event(f"Could not process {filename} (timed out). Continuing without it."))
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
                        metadata={"type": FILE_META_TYPE, "fileId": updated.get("file_id"), "filename": filename},
                    )
                except Exception:
                    logger.exception("Failed to update file memory for '%s' (%s)", filename, memory_id)
        except Exception:
            logger.exception("Unexpected error while processing pending file '%s'", filename)
            events_queue.put(_status_event(f"Could not process {filename}. Continuing without it."))

    logger.warning("[chat] file processing: done, calling add_message next")


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
        logger.warning("[chat] using ephemeral agent bb_assistant_id=%s, agent=%s", agent_bb_assistant_id, ephemeral_agent.get("name", ""))
    elif agent_id and agent_id.startswith("agent_"):
        try:
            agent_bb_assistant_id = run_async(_get_agent_bb_assistant_id(config_assistant_id, agent_id))
            if agent_bb_assistant_id:
                logger.warning("[chat] resolved agent_id=%s -> bb_assistant_id=%s", agent_id, agent_bb_assistant_id)
            else:
                logger.warning("[chat] agent_id=%s has no bb_assistant_id, falling back to default", agent_id)
        except Exception:
            logger.exception("Failed to resolve bb_assistant_id for agent_id=%s", agent_id)

    folder_id = payload.get("folderId", "") if not agent_bb_assistant_id else ""
    folder_bb_assistant_id = ""
    if not agent_bb_assistant_id and folder_id:
            try:
                folder_bb_assistant_id = run_async(_get_folder_bb_assistant_id(config_assistant_id, folder_id))
                if folder_bb_assistant_id:
                    logger.warning("[chat] resolved folder_id=%s -> bb_assistant_id=%s", folder_id, folder_bb_assistant_id)
                else:
                    logger.warning("[chat] folder_id=%s has no bb_assistant_id, falling back to default", folder_id)
            except Exception:
                logger.exception("Failed to resolve bb_assistant_id for folder_id=%s", folder_id)

    thread_owner_id = agent_bb_assistant_id or folder_bb_assistant_id or assistant_id
    thread_id, conversation_id, is_new = get_or_create_thread(thread_owner_id, conversation_id)

    # For new folder conversations, eagerly write hidden conversation_meta so the
    # conversation never leaks into the main list even during the first stream.
    if is_new and folder_id and not agent_bb_assistant_id:
        try:
            run_async(_save_conversation_meta(
                assistant_id,
                conversation_id,
                {"folderId": folder_id, "hidden": True, "title": "New Chat"},
            ))
        except Exception:
            logger.exception("[chat] stream: failed to pre-save folder conversation meta")

    user_text = _extract_user_text(payload)
    model = payload.get("model") or ""
    endpoint = payload.get("endpoint") or payload.get("endpointType") or "bedrock"
    endpoint_option = payload.get("endpointOption", {})
    if not model and endpoint_option:
        model = endpoint_option.get("model", "") or endpoint_option.get("modelLabel", "")

    is_temporary_chat = bool(payload.get("isTemporary"))
    mem_toggle = (
        "Off"
        if is_temporary_chat
        else (
            ephemeral_agent.get("memory", "Off")
            if isinstance(ephemeral_agent, dict)
            else "Off"
        )
    )
    bb_memory = {"Auto": "Auto", "On": "Readonly", "Off": "off"}.get(mem_toggle, "off")
    requested_web_search = (
        "Auto"
        if isinstance(ephemeral_agent, dict) and ephemeral_agent.get("web_search") is True
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
        logger.info("[chat] stream: processing pending files (paths=%s)", requested_paths)
        run_async(_process_pending_files_for_assistant(
            assistant_id=config_assistant_id,
            target_filepaths=requested_paths,
            events_queue=pre_queue,
            response_message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_message_id=str(uuid.uuid4()),
            chat_assistant_id=assistant_id,
        ))

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
        "model": model,
        "endpoint": endpoint,
        "bb_memory": bb_memory,
        "requested_web_search": requested_web_search,
        "pre_queue": pre_queue,
        "mcp_server_map": mcp_server_map,
    }


def _open_backboard_stream(ctx: dict, web_search_mode: str | None):
    """Open the Backboard async stream and return a sync iterator via iter_async."""
    async def _open():
        return await stream_message_proxy_compatible(
            thread_id=ctx["thread_id"],
            content=ctx["user_text"],
            model=ctx["model"] or None,
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

    limit_error = check_token_limit(g.user_id)
    if limit_error:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        user_text = _extract_user_text(payload)
        user_message_id = str(uuid.uuid4())
        error_message_id = str(uuid.uuid4())
        endpoint = payload.get("endpoint") or payload.get("endpointType") or "Nash"
        model = payload.get("model") or ""
        parent_msg_id = payload.get("parentMessageId", "00000000-0000-0000-0000-000000000000")

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
        _q.put({"final": True,
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
                }})
        _streams[stream_id] = {
            "events": _q,
            "done": True,
            "conversationId": conversation_id,
            "userId": g.user_id,
        }
        _log_stream_event(stream_id, "limit_error_stream_created")
        return jsonify({
            "streamId": stream_id,
            "conversationId": conversation_id,
            "status": "started",
        })

    user = find_user_by_id(g.user_id)
    plan = get_user_plan(user)
    requested_model = _extract_requested_model(payload)
    if plan == "free" and requested_model and not _is_free_tier_model(requested_model):
        return (
            jsonify({
                "error": "This model requires a paid plan. Select a free model or upgrade in Settings -> Billing.",
                "code": "premium_model_requires_upgrade",
            }),
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

    return jsonify({
        "streamId": stream_id,
        "conversationId": conversation_id,
        "status": "started",
    })


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
        conversation_id = stream_state.get("conversationId", "")

        try:
            ctx = _prepare_stream(stream_id, user_id, payload)
        except Exception as e:
            logger.exception("[chat] stream: prepare failed for stream_id=%s", stream_id)
            yield f"data: {json.dumps({'final': True, 'conversation': {'conversationId': conversation_id}, 'requestMessage': None, 'responseMessage': {'text': f'Error: {e}', 'error': True}})}\n\n"
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
        parent_message_id = payload.get("parentMessageId", "00000000-0000-0000-0000-000000000000")
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

        # Drain any file-processing status events first.
        pre_q: queue.Queue = ctx["pre_queue"]
        while not pre_q.empty():
            yield f"data: {json.dumps(pre_q.get_nowait())}\n\n"

        mcp_server_map = ctx.get("mcp_server_map", {})

        logger.warning(
            "[chat] stream: opening Backboard stream (thread_id=%s, model=%r, memory=%s, web_search=%r, mcp_servers=%s)",
            thread_id, model, ctx["bb_memory"], ctx["requested_web_search"], list(mcp_server_map.keys()),
        )

        if mcp_server_map:
            # MCP path: use non-streaming tool loop, then fake-stream the result
            try:
                final_answer = run_async(run_with_tool_loop(
                    assistant_id=ctx["assistant_id"],
                    thread_id=thread_id,
                    content=ctx["user_text"],
                    mcp_server_map=mcp_server_map,
                ))
                full_text = final_answer or ""
                total_tokens = (len(ctx["user_text"]) + len(full_text)) // 4 + 1
                # Emit a single streaming chunk so the UI renders progressively
                yield f"data: {json.dumps({'type': 'text', 'text': {'value': full_text}, 'index': 0, 'messageId': response_message_id, 'conversationId': conversation_id, 'userMessageId': user_message_id, 'thread_id': thread_id, 'stream': True})}\n\n"
            except Exception as e:
                logger.exception("[chat] stream: MCP tool loop failed for conversation %s", conversation_id)
                full_text = f"[Error: {e}]"
        else:
            def _consume(web_search_mode):
                nonlocal full_text, total_tokens
                stream_started = time.monotonic()
                chunk_count = 0
                for chunk in _open_backboard_stream(ctx, web_search_mode):
                    if time.monotonic() - stream_started >= STREAM_TOTAL_TIMEOUT_SEC:
                        logger.warning("[chat] stream: total timeout after %ss", STREAM_TOTAL_TIMEOUT_SEC)
                        full_text += "\n\n[Error: response timed out]"
                        return
                    chunk_type = chunk.get("type", "")
                    if chunk_type == "content_streaming":
                        content = chunk.get("content", "")
                        full_text += content
                        chunk_count += 1
                        if chunk_count <= 3:
                            logger.warning("[chat] stream: chunk %d len=%d", chunk_count, len(content))
                        yield {
                            "type": "text",
                            "text": {"value": full_text},
                            "index": 0,
                            "messageId": response_message_id,
                            "conversationId": conversation_id,
                            "userMessageId": user_message_id,
                            "thread_id": thread_id,
                            "stream": True,
                        }
                    elif chunk_type in ("run_ended", "run_completed"):
                        total_tokens = int(chunk.get("total_tokens", 0) or 0)
                        logger.warning("[chat] stream: %s, total_tokens=%d", chunk_type, total_tokens)
                        return
                    elif chunk_type in ("error", "run_failed"):
                        error_msg = chunk.get("error") or chunk.get("message", "Unknown error")
                        raise BackboardAPIError(error_msg)

            try:
                try:
                    for event in _consume(ctx["requested_web_search"]):
                        yield f"data: {json.dumps(event)}\n\n"
                except BackboardAPIError as e:
                    if ctx["requested_web_search"] and not full_text and _is_tool_use_error(str(e)):
                        logger.warning("[chat] stream: retrying without web_search (model=%r)", model)
                        for event in _consume(None):
                            yield f"data: {json.dumps(event)}\n\n"
                    else:
                        logger.warning("[chat] stream: Backboard API error=%s", e)
                        full_text += f"\n\n[Error: {e}]"
            except Exception as e:
                logger.exception("[chat] stream: failed for conversation %s", conversation_id)
                full_text += f"\n\n[Error: {e}]"

        if total_tokens == 0:
            total_tokens = (len(ctx["user_text"]) + len(full_text)) // 4 + 1

        if total_tokens > 0:
            record_token_usage(user_id, total_tokens)

        response_message = {
            "messageId": response_message_id,
            "conversationId": conversation_id,
            "parentMessageId": (override_parent_message_id or parent_message_id) if is_regenerate else user_message_id,
            "text": full_text,
            "sender": "Nash",
            "isCreatedByUser": False,
            "model": model,
            "endpoint": endpoint,
            "createdAt": now,
            "error": False,
            "unfinished": False,
            "content": [{"type": "text", "text": {"value": full_text}}],
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

        if is_regenerate:
            try:
                bb_msgs = run_async(get_thread_messages(thread_id))
                # Thread ends with: [..., uN, aN, uN_regen, aN_regen]
                # We want aN_regen to share uN as its parent (same as aN), and uN_regen to be skipped.
                if len(bb_msgs) >= 4 and bb_msgs[-1].role == "assistant" and bb_msgs[-2].role == "user":
                    regen_ai_id = bb_msgs[-1].message_id
                    regen_user_id = bb_msgs[-2].message_id
                    original_user_id = bb_msgs[-4].message_id
                    save_regen_graph(ctx["assistant_id"], conversation_id, {
                        regen_ai_id: original_user_id,
                        regen_user_id: "SKIP",
                    })
                    logger.warning("[chat] regen_graph saved regen_ai=%s -> original_user=%s", regen_ai_id, original_user_id)
            except Exception:
                logger.exception("[chat] stream: failed to save regen graph")

        try:
            meta = {"title": title, "endpoint": endpoint, "model": model}
            if ctx.get("folder_id"):
                meta["folderId"] = ctx["folder_id"]
            run_async(_save_conversation_meta(ctx["assistant_id"], conversation_id, meta))
        except Exception:
            logger.exception("[chat] stream: failed to save conversation meta")

        # Remove from _streams BEFORE yielding the final event so the
        # status endpoint returns active=false before the client's
        # useResumeOnLoad can fire.
        _streams.pop(stream_id, None)
        _log_stream_event(stream_id, "stream_complete", totalTokens=total_tokens, responseLength=len(full_text))

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
        sid for sid, s in _streams.items()
        if s.get("userId") == g.user_id and not s.get("done") and s.get("generating")
    ]
    logger.warning("[chat] active_jobs user_id=%s active_ids=%s", g.user_id, active_ids)
    return jsonify({"activeJobIds": active_ids})


@chat_bp.route("/api/agents/chat/status/<conversation_id>", methods=["GET"])
@require_jwt
def chat_status(conversation_id):
    for sid, s in _streams.items():
        if s.get("conversationId") == conversation_id and not s.get("done"):
            _log_stream_event(sid, "status_active_hit", requestedConversationId=conversation_id)
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
