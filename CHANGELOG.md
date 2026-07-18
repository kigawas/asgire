# Changelog

## Unreleased

- `AsyncToSync` now resolves the event loop at call time instead of capturing it at construction, syncing upstream [asgiref#562](https://github.com/django/asgiref/issues/562). A wrapper built while a loop is running no longer binds to that loop, so it cannot deadlock on it later (e.g. pytest-asyncio stopping the loop between tests); the stopped-loop guard from 3.12.0 is kept for the parent-loop (threadlocal) path, which upstream does not guard
- Fix an event loop deadlock when exiting `ThreadSensitiveContext` while its executor thread was still blocked waiting on the event loop, syncing upstream [asgiref#535](https://github.com/django/asgiref/issues/535). The executor is now joined in a dedicated thread rather than blocking the loop (or starving its default executor)

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
