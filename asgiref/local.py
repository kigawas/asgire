import asyncio
import contextvars
import threading
from threading import get_ident
from typing import Any

# Name of the ContextVar backing every non-thread-critical Local.
# asgiref.sync._restore_context uses it to recognize Local storage when it
# deliberately moves a context onto another thread.
_CVAR_NAME = "asgiref.local"

# Non-thread-critical Local data is stored as a (thread_id, data) pair. The
# thread tag lets Local ignore data that leaked into an unrelated thread:
#
# Python 3.14 added ``sys.flags.thread_inherit_context``, enabled by default
# on free-threaded builds. When set, a new thread starts with a copy of the
# spawning thread's context instead of an empty one, so the contextvar backing
# a ``Local`` would otherwise be visible in any thread spawned from one that
# had set it -- breaking the documented "thread-local in sync threads"
# behaviour. asgiref re-homes the storage to the current thread at the points
# where it *intentionally* moves work between threads (see
# ``asgiref.sync._restore_context``); data merely inherited by an unrelated
# thread is never re-homed and so stays isolated.
#
# NOTE: the pair is a plain tuple built with a tuple display, not a class:
# one is constructed on every write, and instantiating even a slotted class
# runs a Python-level __init__ (~100ns) where the display is a single C-level
# op. _restore_context recognizes the storage by the cvar's name instead of
# an isinstance check.


def _rehome(storage: "tuple[int, dict[str, Any]]") -> "tuple[int, dict[str, Any]]":
    """Return a copy of *storage* owned by the current thread."""
    return (get_ident(), storage[1])


class _CVar:
    """Contextvar-backed storage for thread_critical Locals in async threads.

    Each async thread creates its own instance (held on the Local's
    ``threading.local``), so the data is already confined to one thread and
    needs no thread tag; the contextvar provides the per-task isolation. Its
    distinct name also keeps ``_restore_context`` from treating it as
    re-homeable cross-thread storage.
    """

    def __init__(self) -> None:
        self._data: "contextvars.ContextVar[dict[str, Any]]" = contextvars.ContextVar("asgiref.local.thread_critical")

    def __getattr__(self, key):
        storage_object = self._data.get({})
        try:
            return storage_object[key]
        except KeyError:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_data":
            return super().__setattr__(key, value)

        storage_object = self._data.get({}).copy()
        storage_object[key] = value
        self._data.set(storage_object)

    def __delattr__(self, key: str) -> None:
        storage_object = self._data.get({}).copy()
        if key in storage_object:
            del storage_object[key]
            self._data.set(storage_object)
        else:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")


class Local:
    """Local storage for async tasks.

    This is a namespace object (similar to `threading.local`) where data is
    also local to the current async task (if there is one).

    In async threads, local means in the same sense as the `contextvars`
    module - i.e. a value set in an async frame will be visible:

    - to other async code `await`-ed from this frame.
    - to tasks spawned using `asyncio` utilities (`create_task`, `wait_for`,
      `gather` and probably others).
    - to code scheduled in a sync thread using `sync_to_async`

    In "sync" threads (a thread with no async event loop running), the
    data is thread-local, but additionally shared with async code executed
    via the `async_to_sync` utility, which schedules async code in a new thread
    and copies context across to that thread.

    If `thread_critical` is True, then the local will only be visible per-thread,
    behaving exactly like `threading.local` if the thread is sync, and as
    `contextvars` if the thread is async. This allows genuinely thread-sensitive
    code (such as DB handles) to be kept strictly to their initial thread and
    disable the sharing across `sync_to_async` and `async_to_sync` wrapped calls.

    Unlike plain `contextvars` objects, this utility is threadsafe.

    NOTE: no lock is needed anywhere below. ContextVar.get/set are atomic
    C operations that only ever touch the calling thread's current context,
    a Context can never be entered by two threads at once, and the published
    (thread_id, data) snapshots are immutable (copy-on-write) - so no shared
    mutable state exists for a lock to protect.
    """

    # Declared here (set branch-wise in __init__) so each storage keeps a
    # precise type: _storage backs thread_critical mode, _cvar everything else.
    _storage: "threading.local"
    _cvar: "contextvars.ContextVar[tuple[int, dict[str, Any]]]"

    def __init__(self, thread_critical: bool = False) -> None:
        self._thread_critical = thread_critical

        if thread_critical:
            # Thread-local storage
            self._storage = threading.local()
        else:
            # Contextvar storage, inlined on the hot path below
            self._cvar = contextvars.ContextVar(_CVAR_NAME)

    def _thread_critical_storage(self):
        # Resolve the storage object for thread_critical mode. The storage is
        # always local to the current thread.
        is_async = True
        try:
            # this is a test for are we in a async or sync
            # thread - will raise RuntimeError if there is
            # no current loop
            asyncio.get_running_loop()
        except RuntimeError:
            is_async = False
        if not is_async:
            # We are in a sync thread, the storage is
            # just the plain thread local (i.e, "global within
            # this thread" - it doesn't matter where you are
            # in a call stack you see the same storage)
            return self._storage
        # We are in an async thread - storage is still
        # local to this thread, but additionally should
        # behave like a context var (is only visible with
        # the same async call stack)

        # Ensure context exists in the current thread
        if not hasattr(self._storage, "cvar"):
            self._storage.cvar = _CVar()

        # self._storage is a thread local, so the members
        # can't be accessed in another thread (we don't
        # need any locks)
        return self._storage.cvar

    # NOTE: the non-thread-critical branches below inline the tagged-tuple
    # storage access instead of dispatching through a storage object: `Local`
    # sits on hot paths (e.g. AsyncToSync.executors) and the indirection costs
    # a failed attribute lookup plus a Python-level frame on every access.
    # Storage owned by another thread was inherited by this thread (rather
    # than intentionally moved here by asgiref) and must not be visible, so
    # each accessor checks the tag before touching the data.

    def __getattr__(self, key):
        if self._thread_critical:
            return getattr(self._thread_critical_storage(), key)
        storage = self._cvar.get(None)
        if storage is not None and storage[0] == get_ident():
            try:
                return storage[1][key]
            except KeyError:
                pass
        raise AttributeError(f"{self!r} object has no attribute {key!r}")

    def __setattr__(self, key, value):
        if key in ("_local", "_storage", "_cvar", "_thread_critical"):
            return super().__setattr__(key, value)
        if self._thread_critical:
            return setattr(self._thread_critical_storage(), key, value)
        ident = get_ident()
        storage = self._cvar.get(None)
        data = storage[1].copy() if storage is not None and storage[0] == ident else {}
        data[key] = value
        self._cvar.set((ident, data))

    def __delattr__(self, key):
        if self._thread_critical:
            return delattr(self._thread_critical_storage(), key)
        ident = get_ident()
        storage = self._cvar.get(None)
        if storage is not None and storage[0] == ident and key in storage[1]:
            data = storage[1].copy()
            del data[key]
            self._cvar.set((ident, data))
        else:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")
