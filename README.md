# asgire

[![License](https://img.shields.io/github/license/kigawas/asgire.svg)](https://github.com/kigawas/asgire)
[![PyPI](https://img.shields.io/pypi/v/asgire.svg)](https://pypi.org/project/asgire/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/asgire)](https://pypistats.org/packages/asgire)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/asgire.svg)](https://pypi.org/project/asgire/)
[![CI](https://img.shields.io/github/actions/workflow/status/kigawas/asgire/ci.yml?branch=main)](https://github.com/kigawas/asgire/actions)
[![Codecov](https://img.shields.io/codecov/c/github/kigawas/asgire.svg)](https://codecov.io/gh/kigawas/asgire)

The revamped and modernized drop-in replacement for [asgiref](https://pypi.org/project/asgiref/).

Same license, same API, but with **better code, comprehensive coverage, and active maintenance**.

## Installation

```bash
pip install asgire
```

The import stays `import asgiref` — no code changes needed.

## Migration

```bash
pip uninstall asgiref
pip install asgire
```

If you need to force Django or other libraries to depend on `asgire` instead of `asgiref` with `uv`, add the following to your `pyproject.toml`:

```toml
[tool.uv]
override-dependencies = ["asgiref ; python_version == '0'"]
```

This will eliminate all transitive dependencies on `asgiref` in `uv.lock` to ensure `asgire` is the only `import asgiref` provider.

## Performance tips

The cost of `sync_to_async` / `async_to_sync` is paid per *boundary crossing* (a
thread hop through the event loop, tens of microseconds), not per line — so the
order below is roughly the order of impact.

Django's `a`-prefixed methods (e.g. `aget`, `acreate`) also carry the implicit
cost of calling `sync_to_async` on the ORM call, so they are not free. Each one
is a boundary crossing. Consider implementing the DB logic in a sync function,
then wrapping it once with `sync_to_async` (two crossings collapse into one,
~2x faster for cheap queries):

```python
# Slower — every a* method is its own sync_to_async crossing
async def log_login(user_id: int):
    user = await User.objects.aget(id=user_id)
    await AuthLog.objects.acreate(user=user, action="logged in")

# Faster — implement the logic in sync, then wrap it once
@sync_to_async
def log_login(user_id: int):
    user = User.objects.get(id=user_id)
    AuthLog.objects.create(user=user, action="logged in")
```

The sync body cannot `await`, so this applies when the block is pure sync work —
and as a bonus, `transaction.atomic` works naturally inside it, which it does
not across `await` boundaries.

### Minimize boundary crossings

Cross as few times as possible. The biggest wins come from restructuring, not
from micro-optimizing each call.

**Batch sync work into one crossing** instead of awaiting in a loop:

```python
# N crossings
for row in rows:
    await sync_to_async(row.save)()

# One crossing
@sync_to_async
def save_all(rows):
    for row in rows:
        row.save()

await save_all(rows)
```

**Resolve sync data while you are still in sync context.** A common Django
antipattern bridges into async and then immediately bounces back to sync for ORM
access. Signals run in sync context where the DB connection is already
available, so read what you need there and pass plain objects to the async
layer:

```python
# Bounces sync -> async -> sync -> async (three+ crossings)
@receiver(post_save, sender=IPAddress)
def on_saved(sender, instance, **kwargs):
    async_to_sync(notify)(instance)

async def notify(instance):
    user = await sync_to_async(lambda: instance.user)()
    organization = await sync_to_async(lambda: instance.organization)()
    await send_email(user, organization)

# Read the ORM data in the sync signal; hand plain objects to async (one crossing)
@receiver(post_save, sender=IPAddress)
def on_saved(sender, instance, **kwargs):
    user = instance.user
    organization = instance.organization
    async_to_sync(notify)(user, organization)

async def notify(user, organization):
    await send_email(user, organization)
```

**Defer I/O triggered by signals.** Sending email or calling an external API
inside a signal runs it inside the transaction (it can fire even if the
transaction later rolls back) and on the request's hot path. Prefer enqueuing
the work to run after commit:

```python
@receiver(post_save, sender=IPAddress)
def on_saved(sender, instance, **kwargs):
    user, organization = instance.user, instance.organization
    transaction.on_commit(lambda: notify_task.delay(user.id, organization.id))
```

### Reuse wrappers instead of building them inline

`sync_to_async(func)` / `async_to_sync(func)` validate and wrap the callable on
construction (~2 µs). Calling them inline rebuilds the wrapper on every call:

```python
# Slower — a fresh wrapper is constructed on every request
async def view():
    return await sync_to_async(do_work)()

# Faster — build the wrapper once and reuse it
do_work_async = sync_to_async(do_work)

async def view():
    return await do_work_async()
```

### Choose `thread_sensitive` deliberately

`sync_to_async` defaults to `thread_sensitive=True`, which runs every call on a
single shared thread. That is required for thread-affine code (e.g. the Django
ORM or anything using thread-locals), but it serializes calls. For sync work
that is independent and thread-safe, pass `thread_sensitive=False` so calls run
concurrently in a thread pool:

```python
# Serialized on one shared thread (safe for thread-affine code)
await sync_to_async(orm_call)()

# Runs concurrently in a pool (use only for independent, thread-safe work)
await sync_to_async(cpu_bound, thread_sensitive=False)()
```

## Development

```bash
uv sync
uv run pytest -v
uv run ruff check --fix
uv run ruff format
uv run ty check
```
