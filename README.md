# asgire

A revamped and modernized drop-in replacement for [asgiref](https://pypi.org/project/asgiref/).

Same license, same API, better code and maintenance.

## Installation

```bash
pip install asgire
```

If migrating from the original:

```bash
pip uninstall asgiref
pip install asgire
```

The import stays `import asgiref` — no code changes needed.

## Development

```bash
uv sync
uv run pytest -v
uv run ruff check .
uv run ty check
```
