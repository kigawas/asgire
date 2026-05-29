# NEWLY ADDED
from asgiref.compatibility import guarantee_single_callable, is_double_callable


class MarkedSingleCallable:
    _asgi_single_callable = True

    def __call__(self, scope):
        pass


class MarkedDoubleCallable:
    _asgi_double_callable = True

    async def __call__(self, scope, receive, send):
        pass


def test_asgi_single_callable_marker():
    app = MarkedSingleCallable()
    assert is_double_callable(app) is False


def test_asgi_double_callable_marker():
    app = MarkedDoubleCallable()
    assert is_double_callable(app) is True


def test_guarantee_single_callable_passthrough():
    async def app(scope, receive, send):
        pass

    result = guarantee_single_callable(app)
    assert result is app


def test_guarantee_single_callable_wraps_double():
    def app(scope):
        async def inner(receive, send):
            pass

        return inner

    result = guarantee_single_callable(app)
    assert result is not app


def test_non_callable_object():
    # An object with no __call__ skips the inner coroutine check and is
    # treated as double-callable.
    class NoCall:
        pass

    assert is_double_callable(NoCall()) is True
