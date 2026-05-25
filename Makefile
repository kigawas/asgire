.PHONY: release clean test lint typecheck fmt

clean:
	rm -rf build/ dist/ asgiref.egg-info/

test:
	uv run pytest -v

lint:
	uv run ruff check .

typecheck:
	uv run ty check

fmt:
	uv run ruff format .
	uv run ruff check --fix .

release: clean
	uv build
	uv publish
