import asyncio

import pytest

from asgiref.timeout import timeout


@pytest.mark.asyncio
async def test_sync_context_manager():
    with timeout(1.0):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_async_context_manager():
    async with timeout(1.0):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_timeout_none_disables():
    with timeout(None):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_timeout_fires():
    with pytest.raises(asyncio.TimeoutError):
        with timeout(0.01):
            await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_timeout_zero_fires_immediately():
    with pytest.raises(asyncio.TimeoutError):
        with timeout(0):
            await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_expired_property():
    t = timeout(0.01)
    assert t.expired is False
    with pytest.raises(asyncio.TimeoutError):
        with t:
            await asyncio.sleep(10)
    assert t.expired is True


@pytest.mark.asyncio
async def test_remaining_property():
    t = timeout(10.0)
    with t:
        assert t.remaining is not None
        assert t.remaining > 0
    t2 = timeout(None)
    assert t2.remaining is None


@pytest.mark.asyncio
async def test_deprecated_loop_parameter():
    loop = asyncio.get_running_loop()
    with pytest.warns(DeprecationWarning):
        timeout(1.0, loop=loop)


@pytest.mark.asyncio
async def test_timeout_outside_task():
    with pytest.raises(RuntimeError, match="inside a task"):
        # Manually call _do_enter without a running task by clearing current_task
        t = timeout(1.0)
        t._task = None
        t._loop = asyncio.get_running_loop()
        # Force _do_enter to see no current task
        original = asyncio.current_task
        try:
            asyncio.current_task = lambda *a: None  # type: ignore[assignment]
            t._do_enter()
        finally:
            asyncio.current_task = original  # type: ignore[assignment]
