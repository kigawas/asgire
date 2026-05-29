# NEWLY ADDED
"""thread_sensitive=True uses a single-thread executor, so two blocking
sync_to_async calls that depend on each other will deadlock. This test
asserts that the deadlock occurs (as a timeout), documenting the limitation."""

import asyncio
import multiprocessing

import pytest

from asgiref.sync import sync_to_async
from asgiref.timeout import timeout


@pytest.mark.asyncio
async def test_thread_sensitive_deadlocks_on_cross_dependent_blocking_calls():
    event = multiprocessing.Event()

    async def waiter():
        await sync_to_async(event.wait)()

    async def setter():
        await asyncio.sleep(0.1)
        await sync_to_async(event.set)()

    asyncio.ensure_future(setter())

    with pytest.raises(asyncio.TimeoutError):
        async with timeout(0.5):
            await waiter()

    # Unblock so the setter task can finish cleanly
    event.set()
