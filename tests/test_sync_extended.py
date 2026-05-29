import asyncio
import sys
import threading

import pytest

from asgiref.sync import async_to_sync, sync_to_async


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
    from concurrent.futures import ThreadPoolExecutor

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
