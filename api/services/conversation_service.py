"""Conversation/thread management backed by Backboard."""
import json
from datetime import datetime, timezone

from api.services.backboard_service import get_client
from api.services.async_runner import run_async

THREAD_MAP_TYPE = "thread_mapping"

_thread_map: dict[str, str] = {}
_loaded_assistants: set[str] = set()


async def _load_thread_mappings(assistant_id: str) -> None:
    if assistant_id in _loaded_assistants:
        return
    client = get_client()
    response = await client.get_memories(assistant_id)
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != THREAD_MAP_TYPE:
            continue
        cid = meta.get("conversationId", "")
        tid = meta.get("threadId", "")
        if cid and tid and cid not in _thread_map:
            _thread_map[cid] = tid
    _loaded_assistants.add(assistant_id)


async def _get_or_create_thread(assistant_id: str, conversation_id: str | None = None) -> tuple[str, str, bool]:
    """Returns (thread_id, conversation_id, is_new)."""
    await _load_thread_mappings(assistant_id)
    client = get_client()

    if conversation_id:
        existing_tid = _thread_map.get(conversation_id)
        if existing_tid:
            return existing_tid, conversation_id, False

    thread = await client.create_thread(assistant_id)
    thread_id = str(thread.thread_id)

    if not conversation_id:
        conversation_id = thread_id

    _thread_map[conversation_id] = thread_id

    await client.add_memory(
        assistant_id=assistant_id,
        content=f"{conversation_id}->{thread_id}",
        metadata={
            "type": THREAD_MAP_TYPE,
            "conversationId": conversation_id,
            "threadId": thread_id,
        },
    )
    return thread_id, conversation_id, True


def get_or_create_thread(assistant_id: str, conversation_id: str | None = None) -> tuple[str, str, bool]:
    return run_async(_get_or_create_thread(assistant_id, conversation_id))


def get_thread_id_for_conversation(conversation_id: str, assistant_id: str | None = None) -> str | None:
    if assistant_id and assistant_id not in _loaded_assistants:
        run_async(_load_thread_mappings(assistant_id))
    return _thread_map.get(conversation_id)


CONVO_META_TYPE = "conversation_meta"


async def _save_conversation_meta(assistant_id: str, conversation_id: str, meta: dict) -> None:
    client = get_client()
    existing = await client.get_memories(assistant_id)
    for m in existing.memories:
        mm = m.metadata or {}
        if mm.get("type") == CONVO_META_TYPE and mm.get("conversationId") == conversation_id:
            await client.update_memory(
                assistant_id=assistant_id,
                memory_id=m.id,
                content=json.dumps(meta),
                metadata={**mm, **{"updatedAt": datetime.now(timezone.utc).isoformat()}},
            )
            return

    await client.add_memory(
        assistant_id=assistant_id,
        content=json.dumps(meta),
        metadata={
            "type": CONVO_META_TYPE,
            "conversationId": conversation_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )


def save_conversation_meta(assistant_id: str, conversation_id: str, meta: dict) -> None:
    run_async(_save_conversation_meta(assistant_id, conversation_id, meta))


async def _list_conversations(assistant_id: str) -> list[dict]:
    client = get_client()
    response = await client.get_memories(assistant_id)
    convos = []
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") != CONVO_META_TYPE:
            continue
        try:
            convo = json.loads(m.content)
            convo["conversationId"] = meta.get("conversationId", "")
            convo["createdAt"] = meta.get("createdAt", "")
            convo["updatedAt"] = meta.get("updatedAt", "")
            convo["_memory_id"] = m.id
            convos.append(convo)
        except json.JSONDecodeError:
            continue
    convos.sort(key=lambda c: c.get("updatedAt", ""), reverse=True)
    return convos


def list_conversations(assistant_id: str) -> list[dict]:
    return run_async(_list_conversations(assistant_id))


async def _delete_conversation_meta(assistant_id: str, conversation_id: str) -> bool:
    client = get_client()
    response = await client.get_memories(assistant_id)
    for m in response.memories:
        meta = m.metadata or {}
        if meta.get("type") == CONVO_META_TYPE and meta.get("conversationId") == conversation_id:
            await client.delete_memory(assistant_id=assistant_id, memory_id=m.id)
            return True
    return False


def delete_conversation_meta(assistant_id: str, conversation_id: str) -> bool:
    return run_async(_delete_conversation_meta(assistant_id, conversation_id))
