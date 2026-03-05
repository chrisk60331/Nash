"""Chat streaming via Backboard.

Implements the resumable SSE pattern the frontend expects:
  POST /api/agents/chat      -> start stream, return {streamId, conversationId}
  GET  /api/agents/chat/stream/:streamId -> SSE event stream
"""
import uuid
import json
import threading
import time
import os
import asyncio
import logging
from collections import deque

from flask import Blueprint, request, jsonify, g, Response

from backboard import DocumentStatus
from backboard.exceptions import BackboardAPIError, BackboardValidationError
from api.middleware.jwt_auth import require_jwt
from api.services.backboard_service import get_client
from api.services.async_runner import run_async
from api.services.user_service import get_user_assistant_id, get_user_config_assistant_id
from api.services.conversation_service import (
    get_or_create_thread,
    save_conversation_meta,
    _save_conversation_meta,
)
from api.services.token_service import check_token_limit, record_token_usage

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


def _extract_user_text(payload: dict) -> str:
    text = payload.get("text", "")
    if not text:
        messages = payload.get("messages", [])
        if messages:
            last = messages[-1] if isinstance(messages, list) else {}
            text = last.get("text", "") or last.get("content", "")
    return text


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
    stream_state: dict,
    response_message_id: str,
    conversation_id: str,
    user_message_id: str,
    chat_assistant_id: str = "",
):
    phase_deadline = time.monotonic() + FILE_PROCESSING_PHASE_TIMEOUT_SEC

    def phase_timed_out() -> bool:
        return time.monotonic() >= phase_deadline

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
            stream_state["events"].append({
                "type": "text",
                "text": {"value": "Document processing time limit reached. Continuing with reply."},
                "index": 0,
                "messageId": response_message_id,
                "conversationId": conversation_id,
                "userMessageId": user_message_id,
                "stream": True,
            })
            return
        filename = f.get("filename", "file")
        try:
            status_text = f"Processing attached files ({i}/{len(pending_files)}): {filename}"
            stream_state["events"].append({
                "type": "text",
                "text": {"value": status_text},
                "index": 0,
                "messageId": response_message_id,
                "conversationId": conversation_id,
                "userMessageId": user_message_id,
                "stream": True,
            })

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
                logger.warning(
                    "[chat] file processing: upload timed out after %ds for '%s'",
                    FILE_UPLOAD_TIMEOUT_SEC,
                    filename,
                )
                stream_state["events"].append({
                    "type": "text",
                    "text": {"value": f"Could not process {filename} (upload timed out). Continuing without it."},
                    "index": 0,
                    "messageId": response_message_id,
                    "conversationId": conversation_id,
                    "userMessageId": user_message_id,
                    "stream": True,
                })
                continue
            except Exception as e:
                logger.exception(
                    "Failed uploading pending file '%s' for assistant %s from %s",
                    filename,
                    assistant_id,
                    filepath,
                )
                stream_state["events"].append({
                    "type": "text",
                    "text": {"value": f"Could not process {filename} ({e}). Continuing without it."},
                    "index": 0,
                    "messageId": response_message_id,
                    "conversationId": conversation_id,
                    "userMessageId": user_message_id,
                    "stream": True,
                })
                continue

            logger.info("[chat] file processing: uploaded '%s', document_id=%s, polling for indexed ...", filename, doc.document_id)

            for attempt in range(FILE_POLL_MAX_ATTEMPTS):
                if phase_timed_out():
                    logger.warning("[chat] file processing: phase time limit during poll for '%s'", filename)
                    stream_state["events"].append({
                        "type": "text",
                        "text": {"value": f"Still processing {filename}. Continuing with reply."},
                        "index": 0,
                        "messageId": response_message_id,
                        "conversationId": conversation_id,
                        "userMessageId": user_message_id,
                        "stream": True,
                    })
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
                    stream_state["events"].append({
                        "type": "text",
                        "text": {"value": f"Could not process {filename} ({msg}). Continuing without it."},
                        "index": 0,
                        "messageId": response_message_id,
                        "conversationId": conversation_id,
                        "userMessageId": user_message_id,
                        "stream": True,
                    })
                    doc = None
                    break
                await asyncio.sleep(FILE_POLL_INTERVAL_SEC)
            else:
                logger.warning("[chat] file processing: timed out waiting for '%s'", filename)
                stream_state["events"].append({
                    "type": "text",
                    "text": {"value": f"Could not process {filename} (timed out). Continuing without it."},
                    "index": 0,
                    "messageId": response_message_id,
                    "conversationId": conversation_id,
                    "userMessageId": user_message_id,
                    "stream": True,
                })
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
                    # Keep chat flow alive even if memory status persistence fails.
                    logger.exception("Failed to update file memory for '%s' (%s)", filename, memory_id)
        except Exception:
            # Final guard: file-processing must never break message generation.
            logger.exception("Unexpected error while processing pending file '%s'", filename)
            stream_state["events"].append({
                "type": "text",
                "text": {"value": f"Could not process {filename}. Continuing without it."},
                "index": 0,
                "messageId": response_message_id,
                "conversationId": conversation_id,
                "userMessageId": user_message_id,
                "stream": True,
            })

    logger.warning("[chat] file processing: done, calling add_message next")


def _run_stream_background(stream_id: str, user_id: str, payload: dict):
    """Run the Backboard stream in a background thread, buffering events."""
    stream_state = _streams[stream_id]

    try:
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

        thread_owner_id = agent_bb_assistant_id or config_assistant_id
        thread_id, conversation_id, is_new = get_or_create_thread(thread_owner_id, conversation_id)
        stream_state["conversationId"] = conversation_id
    except Exception as e:
        stream_state["events"].append({
            "final": True,
            "conversation": {"conversationId": stream_state.get("conversationId", "")},
            "requestMessage": None,
            "responseMessage": {"text": f"Error: {str(e)}", "error": True},
        })
        stream_state["done"] = True
        return

    user_text = _extract_user_text(payload)
    model = payload.get("model") or ""
    endpoint = payload.get("endpoint") or payload.get("endpointType") or "AWS Bedrock"
    endpoint_option = payload.get("endpointOption", {})
    if not model and endpoint_option:
        model = endpoint_option.get("model", "") or endpoint_option.get("modelLabel", "")

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    user_message_id = str(uuid.uuid4())
    response_message_id = str(uuid.uuid4())
    parent_message_id = payload.get("parentMessageId", "00000000-0000-0000-0000-000000000000")

    user_message = {
        "messageId": user_message_id,
        "conversationId": conversation_id,
        "parentMessageId": parent_message_id,
        "text": user_text,
        "sender": "User",
        "isCreatedByUser": True,
        "createdAt": now,
        "error": False,
    }

    stream_state["events"].append({
        "created": True,
        "message": user_message,
    })

    async def _do_stream():
        client = get_client()
        full_text = ""
        total_tokens = 0
        logger.warning("[chat] stream: _do_stream started (thread_id=%s)", thread_id)
        try:
            requested_files = payload.get("files", [])
            requested_paths = {
                f.get("filepath", "")
                for f in requested_files
                if isinstance(f, dict) and f.get("filepath")
            }
            logger.info("[chat] stream: processing pending files (paths=%s)", requested_paths)
            await _process_pending_files_for_assistant(
                assistant_id=config_assistant_id,
                target_filepaths=requested_paths,
                stream_state=stream_state,
                response_message_id=response_message_id,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                chat_assistant_id=assistant_id,
            )
            logger.warning("[chat] stream: calling add_message(thread_id=%s, stream=True) ...", thread_id)
            stream_response = await client.add_message(
                thread_id=thread_id,
                content=user_text,
                stream=True,
            )
            logger.warning("[chat] stream: add_message returned, consuming stream ...")
            stream_started = time.monotonic()
            stream_iter = stream_response.__aiter__()
            chunk_count = 0
            while True:
                if time.monotonic() - stream_started >= STREAM_TOTAL_TIMEOUT_SEC:
                    logger.warning(
                        "Chat stream total timeout for conversation %s after %ss",
                        conversation_id,
                        STREAM_TOTAL_TIMEOUT_SEC,
                    )
                    full_text += "\n\n[Error: response timed out]"
                    break
                try:
                    chunk = await asyncio.wait_for(
                        stream_iter.__anext__(),
                        timeout=STREAM_IDLE_TIMEOUT_SEC,
                    )
                except StopAsyncIteration:
                    logger.info("[chat] stream: StopAsyncIteration (stream ended)")
                    break
                except asyncio.TimeoutError:
                    logger.warning(
                        "Chat stream idle timeout for conversation %s after %ss",
                        conversation_id,
                        STREAM_IDLE_TIMEOUT_SEC,
                    )
                    full_text += "\n\n[Error: response timed out]"
                    break
                except BackboardAPIError as e:
                    logger.warning(
                        "[chat] stream: Backboard API error status=%s msg=%s",
                        getattr(e, "status_code", None),
                        str(e),
                    )
                    full_text += f"\n\n[Error: {str(e)}]"
                    break

                chunk_type = chunk.get("type", "")
                if chunk_type == "content_streaming":
                    content = chunk.get("content", "")
                    full_text += content
                    chunk_count += 1
                    if chunk_count <= 2:
                        logger.warning("[chat] stream: chunk %d type=%s len=%d", chunk_count, chunk_type, len(content))
                    stream_state["events"].append({
                        "type": "text",
                        "text": {"value": full_text},
                        "index": 0,
                        "messageId": response_message_id,
                        "conversationId": conversation_id,
                        "userMessageId": user_message_id,
                        "thread_id": thread_id,
                        "stream": True,
                    })
                elif chunk_type in ("run_ended", "run_completed"):
                    total_tokens = int(chunk.get("total_tokens", 0) or 0)
                    logger.warning("[chat] stream: %s, total_tokens=%d", chunk_type, total_tokens)
                    break
                elif chunk_type in ("error", "run_failed"):
                    error_msg = chunk.get("error") or chunk.get("message", "Unknown error")
                    full_text += f"\n\n[Error: {error_msg}]"
                    break
        except Exception as e:
            logger.exception("Chat stream failed for conversation %s", conversation_id)
            full_text += f"\n\n[Error: {str(e)}]"

        if total_tokens == 0:
            estimated = (len(user_text) + len(full_text)) // 4 + 1
            total_tokens = estimated

        stream_state["_total_tokens"] = total_tokens

        response_message = {
            "messageId": response_message_id,
            "conversationId": conversation_id,
            "parentMessageId": user_message_id,
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

        stream_state["events"].append({
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
        })

        title = full_text[:60].replace("\n", " ").strip()
        if not title:
            title = "New Chat"
        elif len(full_text) > 60:
            title += "..."

        await _save_conversation_meta(config_assistant_id, conversation_id, {
            "title": title,
            "endpoint": endpoint,
            "model": model,
        })

        stream_state["done"] = True

    try:
        run_async(_do_stream())
    except Exception as e:
        stream_state["events"].append({
            "final": True,
            "conversation": {"conversationId": conversation_id},
            "requestMessage": user_message,
            "responseMessage": {"text": f"Error: {str(e)}", "error": True},
        })
        stream_state["done"] = True

    tokens_used = stream_state.pop("_total_tokens", 0)
    if tokens_used > 0:
        record_token_usage(user_id, tokens_used)


@chat_bp.route("/api/agents/chat", methods=["POST"])
@chat_bp.route("/api/agents/chat/<endpoint_name>", methods=["POST"])
@require_jwt
def start_chat(endpoint_name=None):
    payload = request.get_json() or {}
    stream_id = str(uuid.uuid4())
    conversation_id = payload.get("conversationId", "")

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

        _streams[stream_id] = {
            "events": deque([
                {"created": True, "message": user_message},
                {"final": True,
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
                 }},
            ]),
            "done": True,
            "conversationId": conversation_id,
            "userId": g.user_id,
        }
        return jsonify({
            "streamId": stream_id,
            "conversationId": conversation_id,
            "status": "started",
        })

    _streams[stream_id] = {
        "events": deque(),
        "done": False,
        "conversationId": conversation_id,
        "userId": g.user_id,
    }

    thread = threading.Thread(
        target=_run_stream_background,
        args=(stream_id, g.user_id, payload),
        daemon=True,
    )
    thread.start()

    time.sleep(0.1)

    return jsonify({
        "streamId": stream_id,
        "conversationId": _streams[stream_id].get("conversationId", ""),
        "status": "started",
    })


@chat_bp.route("/api/agents/chat/stream/<stream_id>", methods=["GET"])
@require_jwt
def stream_chat(stream_id):
    is_resume = request.args.get("resume") == "true"
    stream_state = _streams.get(stream_id)

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

    def generate():
        while True:
            while stream_state["events"]:
                event = stream_state["events"].popleft()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("final"):
                    _streams.pop(stream_id, None)
                    return

            if stream_state["done"] and not stream_state["events"]:
                _streams.pop(stream_id, None)
                return

            time.sleep(0.05)

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
    active_ids = [sid for sid, s in _streams.items() if s.get("userId") == g.user_id and not s.get("done")]
    return jsonify({"activeJobIds": active_ids})


@chat_bp.route("/api/agents/chat/status/<conversation_id>", methods=["GET"])
@require_jwt
def chat_status(conversation_id):
    for sid, s in _streams.items():
        if s.get("conversationId") == conversation_id and not s.get("done"):
            return jsonify({"active": True, "streamId": sid})
    return jsonify({"active": False})


@chat_bp.route("/api/agents/chat/abort", methods=["POST"])
@require_jwt
def abort_chat():
    data = request.get_json() or {}
    stream_id = data.get("streamId")
    if stream_id and stream_id in _streams:
        _streams[stream_id]["done"] = True
    return jsonify({"message": "Aborted"})


@chat_bp.route("/api/agents/tools/calls", methods=["GET"])
@require_jwt
def tool_calls():
    return jsonify([])
