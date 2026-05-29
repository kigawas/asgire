import asyncio

import pytest

from asgiref.testing import ApplicationCommunicator
from asgiref.wsgi import WsgiToAsgi


def make_scope(**overrides):
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [],
    }
    scope.update(overrides)
    return scope


async def drain(instance):
    """
    Consume the full response so the WSGI worker thread runs to completion.

    Leaving a response half-read keeps the worker thread blocked inside
    ``sync_send`` waiting on the event loop, which prevents the executor from
    joining its threads at shutdown.
    """
    messages = []
    while True:
        message = await instance.receive_output(5)
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body"):
            break
    return messages


@pytest.mark.asyncio
async def test_non_http_scope():
    def wsgi_app(environ, start_response):
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, {"type": "websocket"})
    with pytest.raises(ValueError, match="non-HTTP scope"):
        await instance.send_input({"type": "http.request"})
        await instance.receive_output()


@pytest.mark.asyncio
async def test_non_http_request_message():
    def wsgi_app(environ, start_response):
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope())
    await instance.send_input({"type": "http.disconnect"})
    with pytest.raises(ValueError, match="non-HTTP-request message"):
        await instance.receive_output(timeout=0.5)


@pytest.mark.asyncio
async def test_server_in_scope():
    def wsgi_app(environ, start_response):
        assert environ["SERVER_NAME"] == "example.com"
        assert environ["SERVER_PORT"] == "8080"
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope(server=("example.com", 8080)))
    await instance.send_input({"type": "http.request"})
    messages = await drain(instance)
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_no_server_in_scope():
    def wsgi_app(environ, start_response):
        assert environ["SERVER_NAME"] == "localhost"
        assert environ["SERVER_PORT"] == "80"
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope())
    await instance.send_input({"type": "http.request"})
    messages = await drain(instance)
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_client_in_scope():
    def wsgi_app(environ, start_response):
        assert environ["REMOTE_ADDR"] == "192.168.1.1"
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope(client=("192.168.1.1", 12345)))
    await instance.send_input({"type": "http.request"})
    messages = await drain(instance)
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_content_type_header():
    def wsgi_app(environ, start_response):
        assert environ["CONTENT_TYPE"] == "text/plain"
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope(headers=[[b"content-type", b"text/plain"]]))
    await instance.send_input({"type": "http.request"})
    messages = await drain(instance)
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_start_response_called_twice_without_exc_info():
    def wsgi_app(environ, start_response):
        start_response("200 OK", [])
        try:
            start_response("200 OK", [])
        except ValueError as e:
            start_response("500 Internal Server Error", [], exc_info=(type(e), e, e.__traceback__))
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope())
    await instance.send_input({"type": "http.request"})
    messages = await drain(instance)
    assert messages[0]["status"] == 500


@pytest.mark.asyncio
async def test_start_response_after_response_started_raises():
    def wsgi_app(environ, start_response):
        start_response("200 OK", [])
        yield b"first"
        # Response has begun; re-calling start_response must re-raise via exc_info
        try:
            raise ValueError("re-raised after start")
        except ValueError as e:
            start_response("500 Error", [], (type(e), e, e.__traceback__))
        yield b"second"

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope())
    await instance.send_input({"type": "http.request"})
    assert (await instance.receive_output(5))["status"] == 200
    assert (await instance.receive_output(5))["body"] == b"first"
    # Let the worker thread resume and raise before we read the failed future
    await asyncio.sleep(0.1)
    with pytest.raises(ValueError, match="re-raised after start"):
        await instance.receive_output(5)
