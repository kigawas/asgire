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
    response = await instance.receive_output()
    assert response["status"] == 200


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
    response = await instance.receive_output()
    assert response["status"] == 200


@pytest.mark.asyncio
async def test_client_in_scope():
    def wsgi_app(environ, start_response):
        assert environ["REMOTE_ADDR"] == "192.168.1.1"
        start_response("200 OK", [])
        return [b"ok"]

    app = WsgiToAsgi(wsgi_app)
    instance = ApplicationCommunicator(app, make_scope(client=("192.168.1.1", 12345)))
    await instance.send_input({"type": "http.request"})
    response = await instance.receive_output()
    assert response["status"] == 200


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
    response = await instance.receive_output()
    assert response["status"] == 500
