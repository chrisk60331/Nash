"""Short-lived cache for Backboard get_memories() results.

During a page load the frontend fires ~8 endpoints that each independently
call get_memories(config_assistant_id).  This cache ensures only the first
one actually hits Backboard; the rest reuse the cached result within the
TTL window.
"""
import threading
import time
from dataclasses import dataclass, field

from api.services.backboard_service import get_client
from api.services.async_runner import run_async

_CACHE_TTL_SECONDS = 5.0


@dataclass
class _CacheEntry:
    memories: list
    ts: float


_cache: dict[str, _CacheEntry] = {}
_inflight: dict[str, threading.Event] = {}
_lock = threading.Lock()


def get_memories_cached(assistant_id: str, *, force: bool = False) -> list:
    """Return memories for *assistant_id*, using a short-lived cache.

    Concurrent callers for the same assistant_id will wait for the first
    caller's result rather than issuing duplicate requests.
    """
    now = time.monotonic()

    with _lock:
        entry = _cache.get(assistant_id)
        if entry and not force and (now - entry.ts) < _CACHE_TTL_SECONDS:
            return entry.memories

        event = _inflight.get(assistant_id)
        if event is not None:
            pass  # another thread is fetching; wait below
        else:
            event = threading.Event()
            _inflight[assistant_id] = event

    if not event.is_set():
        is_fetcher = False
        with _lock:
            if _inflight.get(assistant_id) is event and not event.is_set():
                is_fetcher = True

        if is_fetcher:
            try:
                response = run_async(get_client().get_memories(assistant_id))
                memories = list(response.memories)
                with _lock:
                    _cache[assistant_id] = _CacheEntry(memories=memories, ts=time.monotonic())
            finally:
                event.set()
                with _lock:
                    _inflight.pop(assistant_id, None)
        else:
            event.wait(timeout=30)

    with _lock:
        entry = _cache.get(assistant_id)
    return entry.memories if entry else []


def invalidate(assistant_id: str) -> None:
    """Remove cached memories for an assistant (call after writes)."""
    with _lock:
        _cache.pop(assistant_id, None)
