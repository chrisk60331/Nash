"""Persistent event loop for running async Backboard SDK calls from sync Flask code.

A single event loop lives in a daemon thread for the lifetime of the process.
This avoids the 'Event loop is closed' errors that happen when asyncio.run()
creates and destroys loops, killing the httpx connection pool inside BackboardClient.
"""
import asyncio
import threading
from concurrent.futures import Future

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _start_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop is not None and _loop.is_running():
        return _loop
    with _lock:
        if _loop is not None and _loop.is_running():
            return _loop
        _loop = asyncio.new_event_loop()
        _thread = threading.Thread(target=_start_loop, args=(_loop,), daemon=True)
        _thread.start()
    return _loop


def run_async(coro):
    """Submit a coroutine to the persistent loop and block until it completes."""
    loop = _get_loop()
    future: Future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
