import asyncio

import pytest

from asgiref.testing import ApplicationCommunicator


@pytest.mark.asyncio
async def test_wait_successful():
    async def app(scope, receive, send):
        await send({"type": "done"})

    instance = ApplicationCommunicator(app, {"type": "test"})
    await instance.receive_output()
    await instance.wait(timeout=1)


@pytest.mark.asyncio
async def test_wait_timeout_cancels_app():
    async def app(scope, receive, send):
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            pass

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    await instance.wait(timeout=0.05)
    assert instance.future.done()


@pytest.mark.asyncio
async def test_stop_not_started():
    async def app(scope, receive, send):
        pass

    instance = ApplicationCommunicator(app, {"type": "test"})
    instance.stop()


@pytest.mark.asyncio
async def test_stop_running():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    instance.stop(exceptions=False)


@pytest.mark.asyncio
async def test_stop_with_exception():
    async def app(scope, receive, send):
        raise ValueError("app error")

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    await asyncio.sleep(0.05)
    with pytest.raises(ValueError, match="app error"):
        instance.stop(exceptions=True)


@pytest.mark.asyncio
async def test_send_input_after_app_done():
    async def app(scope, receive, send):
        raise ValueError("app died")

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    await asyncio.sleep(0.05)
    with pytest.raises(ValueError, match="app died"):
        await instance.send_input({"type": "test"})


@pytest.mark.asyncio
async def test_receive_output_timeout_with_failed_app():
    async def app(scope, receive, send):
        await asyncio.sleep(0.02)
        raise ValueError("app crashed")

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    with pytest.raises(ValueError, match="app crashed"):
        await instance.receive_output(timeout=0.05)


@pytest.mark.asyncio
async def test_receive_output_timeout_cancels_running_app():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    with pytest.raises(asyncio.TimeoutError):
        await instance.receive_output(timeout=0.01)


@pytest.mark.asyncio
async def test_del_cleanup():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    instance = ApplicationCommunicator(app, {"type": "test"})
    _ = instance.future
    del instance
