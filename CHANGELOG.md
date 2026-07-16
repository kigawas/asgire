# Changelog

## Unreleased

- `AsyncToSync` now resolves the event loop at call time instead of capturing it at construction, syncing upstream [asgiref#562](https://github.com/django/asgiref/issues/562). A wrapper built while a loop is running no longer binds to that loop, so it cannot deadlock on it later (e.g. pytest-asyncio stopping the loop between tests); the stopped-loop guard from 3.12.0 is kept for the parent-loop (threadlocal) path, which upstream does not guard

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
