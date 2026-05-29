# NEWLY ADDED
import threading

import pytest

from asgiref.current_thread_executor import CurrentThreadExecutor


def test_run_until_future_wrong_thread():
    executor = CurrentThreadExecutor(None)
    from concurrent.futures import Future

    f = Future()

    def run_in_thread():
        with pytest.raises(RuntimeError, match="different thread"):
            executor.run_until_future(f)

    t = threading.Thread(target=run_in_thread)
    t.start()
    t.join()


def test_submit_from_same_thread():
    executor = CurrentThreadExecutor(None)
    with pytest.raises(RuntimeError, match="own thread"):
        executor.submit(lambda: None)


def test_submit_to_broken_executor_chain():
    executor = CurrentThreadExecutor(None)
    # Break the executor
    with executor._work_ready:
        executor._broken = True

    def run_in_thread():
        with pytest.raises(RuntimeError, match="already quit"):
            executor.submit(lambda: None)

    t = threading.Thread(target=run_in_thread)
    t.start()
    t.join()


def test_work_item_exception():
    from concurrent.futures import Future

    from asgiref.current_thread_executor import _WorkItem

    f = Future()
    item = _WorkItem(f, lambda: 1 / 0)
    item.run()
    with pytest.raises(ZeroDivisionError):
        f.result()


def test_work_item_cancelled():
    from concurrent.futures import Future

    from asgiref.current_thread_executor import _WorkItem

    f = Future()
    f.cancel()
    item = _WorkItem(f, lambda: "should not run")
    item.run()
    assert f.cancelled()
