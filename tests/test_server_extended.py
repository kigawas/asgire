# NEWLY ADDED
import asyncio
import logging

import pytest

from asgiref.server import StatelessServer


class SimpleServer(StatelessServer):
    async def handle(self):
        pass

    async def application_send(self, scope, message):
        pass


@pytest.mark.asyncio
async def test_arun_stops_when_handle_returns():
    # When handle() returns (rather than looping), arun raises Done internally
    # and exits cleanly.
    class QuickServer(StatelessServer):
        async def handle(self):
            return

        async def application_checker(self):
            return

        async def application_send(self, scope, message):
            pass

    server = QuickServer(lambda scope: None)
    await server.arun()


def test_run_handles_keyboard_interrupt():
    class KbServer(StatelessServer):
        async def handle(self):
            raise KeyboardInterrupt

        async def application_checker(self):
            return

        async def application_send(self, scope, message):
            pass

    server = KbServer(lambda scope: None)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # run() should catch the KeyboardInterrupt and return without raising
        server.run()
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@pytest.mark.asyncio
async def test_delete_application_instance_with_done_future():
    async def app(scope, receive, send):
        return

    server = SimpleServer(app, max_applications=10)
    server.get_or_create_application_instance("x", {"type": "test"})
    await asyncio.sleep(0.05)
    assert server.application_instances["x"]["future"].done()
    # Future already done → delete skips the cancel branch
    server.delete_application_instance("x")
    assert "x" not in server.application_instances


@pytest.mark.asyncio
async def test_delete_oldest_skips_non_oldest():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    server = SimpleServer(app, max_applications=10)
    server.get_or_create_application_instance("a", {"type": "t"})
    server.get_or_create_application_instance("b", {"type": "t"})
    # Make "b" the oldest even though "a" is iterated first
    server.application_instances["a"]["last_used"] = 1000.0
    server.application_instances["b"]["last_used"] = 1.0
    server.delete_oldest_application_instance()
    assert "a" in server.application_instances
    assert "b" not in server.application_instances
    for details in server.application_instances.values():
        details["future"].cancel()


@pytest.mark.asyncio
async def test_application_checker_skips_running_cleans_finished():
    async def slow(scope, receive, send):
        await asyncio.sleep(100)

    async def quick(scope, receive, send):
        return

    server = SimpleServer(slow, max_applications=10)
    server.get_or_create_application_instance("slow", {"type": "t"})
    server.application = quick
    server.get_or_create_application_instance("quick", {"type": "t"})
    await asyncio.sleep(0.05)

    server.application_checker_interval = 0.01
    checker = asyncio.create_task(server.application_checker())
    await asyncio.sleep(0.05)
    checker.cancel()
    try:
        await checker
    except asyncio.CancelledError:
        pass

    # "slow" still running (not done branch); "quick" finished cleanly (no exception branch)
    assert "slow" in server.application_instances
    assert "quick" not in server.application_instances
    server.application_instances["slow"]["future"].cancel()


@pytest.mark.asyncio
async def test_application_checker_handles_already_deleted():
    class DeletingServer(StatelessServer):
        async def handle(self):
            pass

        async def application_send(self, scope, message):
            pass

        async def application_exception(self, exception, details):
            # Remove the instance before the checker's own del runs, forcing a KeyError
            for sid, candidate in list(self.application_instances.items()):
                if candidate is details:
                    del self.application_instances[sid]

    async def failing(scope, receive, send):
        raise ValueError("boom")

    server = DeletingServer(failing, max_applications=10)
    server.get_or_create_application_instance("x", {"type": "t"})
    await asyncio.sleep(0.05)

    server.application_checker_interval = 0.01
    checker = asyncio.create_task(server.application_checker())
    await asyncio.sleep(0.05)
    checker.cancel()
    try:
        await checker
    except asyncio.CancelledError:
        pass

    assert "x" not in server.application_instances


@pytest.mark.asyncio
async def test_application_checker_cleans_done_futures():
    server = SimpleServer(lambda scope: None, max_applications=10)

    async def failing_app(scope, receive, send):
        raise ValueError("boom")

    server.application = failing_app
    server.get_or_create_application_instance("test-1", {"type": "test"})
    await asyncio.sleep(0.05)

    server.application_checker_interval = 0.01
    checker = asyncio.create_task(server.application_checker())
    await asyncio.sleep(0.05)
    checker.cancel()
    try:
        await checker
    except asyncio.CancelledError:
        pass

    assert "test-1" not in server.application_instances


@pytest.mark.asyncio
async def test_application_exception_logs(caplog):
    server = SimpleServer(lambda scope: None)
    exc = ValueError("test error")
    exc.__traceback__ = None

    with caplog.at_level(logging.ERROR):
        await server.application_exception(exc, {"scope": {}})
    assert "test error" in caplog.text


@pytest.mark.asyncio
async def test_delete_application_instance():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    server = SimpleServer(app, max_applications=10)
    server.get_or_create_application_instance("to-delete", {"type": "test"})
    assert "to-delete" in server.application_instances

    server.delete_application_instance("to-delete")
    assert "to-delete" not in server.application_instances


@pytest.mark.asyncio
async def test_delete_oldest_application_instance():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    server = SimpleServer(app, max_applications=2)
    server.get_or_create_application_instance("old", {"type": "test"})
    await asyncio.sleep(0.01)
    server.get_or_create_application_instance("new", {"type": "test"})

    server.delete_oldest_application_instance()
    assert "old" not in server.application_instances
    assert "new" in server.application_instances

    for details in server.application_instances.values():
        details["future"].cancel()


@pytest.mark.asyncio
async def test_get_or_create_reuses_existing():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    server = SimpleServer(app, max_applications=10)
    q1 = server.get_or_create_application_instance("reuse", {"type": "test"})
    q2 = server.get_or_create_application_instance("reuse", {"type": "test"})
    assert q1 is q2

    for details in server.application_instances.values():
        details["future"].cancel()


@pytest.mark.asyncio
async def test_max_applications_eviction():
    async def app(scope, receive, send):
        await asyncio.sleep(100)

    server = SimpleServer(app, max_applications=1)
    server.get_or_create_application_instance("a", {"type": "test"})
    await asyncio.sleep(0.01)
    server.get_or_create_application_instance("b", {"type": "test"})
    await asyncio.sleep(0.01)
    # Third instance triggers eviction (check is > max_applications)
    server.get_or_create_application_instance("c", {"type": "test"})

    assert len(server.application_instances) <= 2
    assert "c" in server.application_instances

    for details in server.application_instances.values():
        details["future"].cancel()


def test_handle_not_implemented():
    server = StatelessServer(lambda scope: None)
    with pytest.raises(NotImplementedError):
        asyncio.run(server.handle())


def test_application_send_not_implemented():
    server = StatelessServer(lambda scope: None)
    with pytest.raises(NotImplementedError):
        asyncio.run(server.application_send(None, None))
