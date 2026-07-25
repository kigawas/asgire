# Changelog

## Unreleased

- `AsyncToSync` now resolves the event loop at call time instead of capturing it at construction, syncing upstream [asgiref#562](https://github.com/django/asgiref/issues/562). A wrapper built while a loop is running no longer binds to that loop, so it cannot deadlock on it later (e.g. pytest-asyncio stopping the loop between tests); the stopped-loop guard from 3.12.0 is kept for the parent-loop (threadlocal) path, which upstream does not guard
- Fix an event loop deadlock when exiting `ThreadSensitiveContext` while its executor thread was still blocked waiting on the event loop, syncing upstream [asgiref#535](https://github.com/django/asgiref/issues/535). The executor is now joined in a dedicated thread rather than blocking the loop (or starving its default executor)
- Fix `StatelessServer.run()` failing on Python 3.14, where `asyncio.get_event_loop()` no longer creates an event loop if none exists; it now uses `asyncio.run()`, syncing upstream [asgiref#559](https://github.com/django/asgiref/issues/559)
- Fix `Local` leaking data between unrelated sync threads when `sys.flags.thread_inherit_context` is enabled (Python 3.14+, default on free-threaded builds): storage is now tagged with its owning thread and re-homed only when asgiref intentionally moves work across threads, syncing upstream [asgiref#564](https://github.com/django/asgiref/pull/564)
- Run CI against the free-threaded builds of Python 3.13 and 3.14
- Speed up `Local` attribute access well beyond the pre-tagging baseline: the thread tag is a plain inline-built tuple instead of a class instance, the per-access lock is gone (contextvar storage is thread-confined, so there is no shared mutable state to guard), and storage access is flattened into `Local`'s own accessors instead of dispatching through an inner object
- Fix a lost-update race in `AsyncToSync` (in upstream): the finished awaitable's context is now captured before the waiting sync thread is released, so context and `Local` changes made by the async code can no longer be lost when the waiter wakes first. Surfaced as a rare flake on free-threaded builds, where the window is genuinely parallel

## 3.12.2

- Speed up `Local` attribute access ~3x by removing per-access context-manager overhead
- Speed up `sync_to_async(func)` construction for functions/methods by skipping a redundant `iscoroutinefunction` check (helps the inline `await sync_to_async(self.method)(...)` pattern)

## 3.12.1

- Remove Python 3.9 related code completely
- Fix WSGI thread contention bug

## 3.12.0

- Drop Python 3.9 support
- Fix stopped loop deadlock: [asgiref#525](https://github.com/django/asgiref/issues/525)
- Initial release
