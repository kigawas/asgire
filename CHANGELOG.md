# Changelog

## 3.12.2

- Speed up `sync_to_async(func)` construction for functions/methods by skipping a redundant `iscoroutinefunction` check (helps the inline `await sync_to_async(self.method)(...)` pattern)

## 3.12.1

- Remove Python 3.9 related code completely
- Fix WSGI thread contention bug

## 3.12.0

- Drop Python 3.9 support
- Fix stopped loop deadlock: [asgiref#525](https://github.com/django/asgiref/issues/525)
- Initial release
