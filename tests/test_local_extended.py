# NEWLY ADDED
import threading

import pytest

from asgiref.local import Local


def test_concurrent_hammer():
    # Local is lock-free: contextvar storage is thread-confined, so per-thread
    # isolation must hold with no torn state under concurrent get/set/del on
    # one shared instance (true parallelism on free-threaded builds).
    local = Local()
    errors = []
    barrier = threading.Barrier(8, timeout=5)

    def worker(n):
        try:
            barrier.wait()
            for i in range(2000):
                local.value = (n, i)
                assert local.value == (n, i)
                if i % 7 == 0:
                    del local.value
                    assert not hasattr(local, "value")
        except BaseException as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors


def test_delattr_missing_raises():
    local = Local()
    with pytest.raises(AttributeError, match="no attribute"):
        del local.never_set


def test_delattr_after_delete_raises():
    local = Local()
    local.foo = 1
    del local.foo
    with pytest.raises(AttributeError, match="no attribute"):
        del local.foo


def test_delattr_thread_critical():
    # Exercises the thread_critical=True branch of __delattr__.
    local = Local(thread_critical=True)
    local.foo = 1
    assert local.foo == 1
    del local.foo
    with pytest.raises(AttributeError, match="no attribute"):
        local.foo


@pytest.mark.asyncio
async def test_thread_critical_async_get_set_del():
    # In an async thread, thread_critical storage goes through the per-thread
    # _CVar; exercise its get/set/del and both miss paths.
    local = Local(thread_critical=True)
    local.foo = 1
    assert local.foo == 1
    del local.foo
    with pytest.raises(AttributeError, match="no attribute"):
        local.foo
    with pytest.raises(AttributeError, match="no attribute"):
        del local.foo
