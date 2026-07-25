# NEWLY ADDED
import asyncio
import os
import sys
import threading
import time
from concurrent.futures import Future as _Future
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest

from asgiref.local import Local
from asgiref.sync import (
    AsyncToSync,
    SyncToAsync,
    ThreadSensitiveContext,
    async_to_sync,
    sync_to_async,
)


def test_async_to_sync_decorator_form():
    @async_to_sync(force_new_loop=True)
    async def hello():
        return "hello"

    assert hello() == "hello"


def test_sync_to_async_decorator_form():
    @sync_to_async
    def hello():
        return "hello"

    result = asyncio.run(hello())
    assert result == "hello"


def test_async_to_sync_warns_on_non_async():
    with pytest.warns(match="non-async-marked callable"):
        async_to_sync(lambda: None)


def test_async_to_sync_propagates_coroutine_exception():
    async def boom():
        raise ValueError("async boom")

    with pytest.raises(ValueError, match="async boom"):
        async_to_sync(boom)()


def test_async_to_sync_falls_back_when_main_loop_closes_mid_dispatch():
    # Simulates the parent event loop (found via the SyncToAsync threadlocal)
    # closing between the is_running() check and call_soon_threadsafe:
    # AsyncToSync must fall back to a new loop.
    class FakeLoop:
        def is_running(self):
            return True

        def create_task(self, *args):  # read as the scheduled-callback argument
            return None

        def call_soon_threadsafe(self, *args):
            raise RuntimeError("event loop is closed")

    async def coro():
        return "ok"

    SyncToAsync.threadlocal.main_event_loop = FakeLoop()
    SyncToAsync.threadlocal.main_event_loop_pid = os.getpid()
    try:
        assert AsyncToSync(coro)() == "ok"
    finally:
        del SyncToAsync.threadlocal.main_event_loop
        del SyncToAsync.threadlocal.main_event_loop_pid


@pytest.mark.asyncio
async def test_sync_to_async_reuses_registered_loop_executor():
    # When the running loop has a registered thread executor (as async_to_sync
    # sets up for its new loop) and no parent executor is in context, a
    # thread-sensitive sync_to_async reuses it instead of allocating one.
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    AsyncToSync.loop_thread_executors[loop] = executor
    try:
        assert await sync_to_async(lambda: "ok")() == "ok"
    finally:
        del AsyncToSync.loop_thread_executors[loop]
        executor.shutdown(wait=False)


@pytest.mark.asyncio
async def test_sync_to_async_deadlock_guard():
    # When the single-thread executor is already in use in this context, a
    # further thread-sensitive sync_to_async refuses rather than deadlocking.
    SyncToAsync.deadlock_context.set(True)
    try:
        with pytest.raises(RuntimeError, match="would deadlock"):
            await sync_to_async(lambda: None)()
    finally:
        SyncToAsync.deadlock_context.set(False)


@pytest.mark.asyncio
async def test_async_to_sync_captures_context_before_resolving():
    # Regression test for a lost-update race: main_wrap must capture the
    # finished context into context[0] BEFORE resolving call_result, because
    # resolving wakes the sync thread parked in __call__, which reads
    # context[0] immediately. A Future that dawdles on the event loop thread
    # after resolving makes the stale read deterministic on unfixed code; on
    # fixed code it only adds latency.

    class SlowResolveFuture(_Future):
        def set_result(self, result):
            super().set_result(result)
            time.sleep(0.01)

    local = Local()
    local.value = "outer"

    async def inner():
        local.value = "inner"

    def sync_code():
        with mock.patch("asgiref.sync.Future", SlowResolveFuture):
            async_to_sync(inner)()
        return local.value

    assert await sync_to_async(sync_code)() == "inner"
    assert local.value == "inner"


@pytest.mark.asyncio
async def test_thread_sensitive_context_exit_cancelled_while_joining():
    # Covers ThreadSensitiveContext.__aexit__'s InvalidStateError branch:
    # cancelling the task that is awaiting the executor join leaves the join
    # thread to finish later, and its set_result() then finds the future
    # already cancelled.
    started = threading.Event()
    release = threading.Event()
    about_to_exit = asyncio.Event()
    work = {}

    def blocking():
        started.set()
        release.wait(5)

    async def scope():
        async with ThreadSensitiveContext():
            work["task"] = asyncio.create_task(sync_to_async(blocking)())
            while not started.is_set():
                await asyncio.sleep(0.01)
            about_to_exit.set()

    threads_before = set(threading.enumerate())
    scope_task = asyncio.create_task(scope())
    # Event.set() wakes this waiter via call_soon, so by the time wait()
    # returns, scope_task has already run through __aexit__'s synchronous
    # prefix (spawning the join thread) and parked at its await.
    await about_to_exit.wait()
    scope_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await scope_task

    # Unblock the worker: the join thread completes the shutdown and hits
    # set_result on the already-cancelled future. Both threads exiting means
    # that set_result call has happened.
    release.set()
    new_threads = set(threading.enumerate()) - threads_before
    while any(thread.is_alive() for thread in new_threads):
        await asyncio.sleep(0.01)
    await work["task"]


@pytest.mark.asyncio
async def test_sync_to_async_exception_propagation():
    @sync_to_async
    def fail():
        raise ValueError("sync error")

    with pytest.raises(ValueError, match="sync error"):
        await fail()


@pytest.mark.asyncio
async def test_sync_to_async_preserves_exc_info():
    @sync_to_async
    def check_exc_info():
        return sys.exc_info()

    async def outer():
        try:
            raise RuntimeError("outer")
        except RuntimeError:
            return await check_exc_info()

    exc_info = await outer()
    assert exc_info[0] is RuntimeError
    assert str(exc_info[1]) == "outer"


@pytest.mark.asyncio
async def test_sync_to_async_with_executor():

    executor = ThreadPoolExecutor(max_workers=1)

    @sync_to_async(thread_sensitive=False, executor=executor)
    def hello():
        return "hello"

    result = await hello()
    assert result == "hello"
    executor.shutdown(wait=False)


@pytest.mark.asyncio
async def test_async_to_sync_called_from_async_raises():
    async def coro():
        return "hi"

    with pytest.raises(RuntimeError, match="cannot use AsyncToSync"):
        async_to_sync(coro)()


@pytest.mark.asyncio
async def test_sync_to_async_cancellation():
    # threading.Event is loop-independent, so no reliance on asyncio internals
    started = threading.Event()
    release = threading.Event()

    @sync_to_async(thread_sensitive=False)
    def blocking():
        started.set()
        release.wait(timeout=5)
        return "done"

    task = asyncio.create_task(blocking())
    # Poll the threading.Event from the event loop until the worker starts
    while not started.is_set():
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Let the worker thread exit promptly instead of lingering
    release.set()
