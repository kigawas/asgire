"""Regression test: async_to_sync must not hang when the captured
main_event_loop on SyncToAsync.threadlocal is stopped."""

import asyncio
import os
import threading
import time

from asgiref.sync import SyncToAsync, async_to_sync

WATCHDOG_SECONDS = 5


def test_async_to_sync_does_not_hang_when_threadlocal_loop_is_stopped() -> None:
    barrier = threading.Event()
    state: dict = {"result": None, "error": None}

    def _worker() -> None:
        # Plant a stopped loop on this worker's threadlocal
        stale_loop = asyncio.new_event_loop()
        SyncToAsync.threadlocal.main_event_loop = stale_loop
        SyncToAsync.threadlocal.main_event_loop_pid = os.getpid()

        async def hello() -> str:
            return "hello"

        try:
            state["result"] = async_to_sync(hello)()
        except BaseException as exc:
            state["error"] = exc
        finally:
            barrier.set()

    thread = threading.Thread(target=_worker, name="stale-loop-worker", daemon=True)
    start = time.perf_counter()
    thread.start()

    if not barrier.wait(timeout=WATCHDOG_SECONDS):
        elapsed = time.perf_counter() - start
        raise AssertionError(
            f"async_to_sync blocked for {elapsed:.1f}s waiting on a "
            "stopped main_event_loop captured via SyncToAsync.threadlocal "
            "— regression of #525"
        )

    if state["error"] is not None:
        raise state["error"]
    assert state["result"] == "hello"
