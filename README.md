# asgire

[![License](https://img.shields.io/github/license/kigawas/asgire.svg)](https://github.com/kigawas/asgire)
[![PyPI](https://img.shields.io/pypi/v/asgire.svg)](https://pypi.org/project/asgire/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/asgire)](https://pypistats.org/packages/asgire)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/asgire.svg)](https://pypi.org/project/asgire/)
[![CI](https://img.shields.io/github/actions/workflow/status/kigawas/asgire/ci.yml?branch=main)](https://github.com/kigawas/asgire/actions)
[![Codecov](https://img.shields.io/codecov/c/github/kigawas/asgire.svg)](https://codecov.io/gh/kigawas/asgire)

The revamped and modernized drop-in replacement for [asgiref](https://pypi.org/project/asgiref/).

Same license, same API, better code and maintenance.

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

## Development

```bash
uv sync
uv run pytest -v
uv run ruff check --fix
uv run ruff format
uv run ty check
```
