import asyncio
import sys

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
    started = asyncio.Event()

    @sync_to_async
    def slow():
        import time

        started._loop.call_soon_threadsafe(started.set)
        time.sleep(5)
        return "done"

    task = asyncio.create_task(slow())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
