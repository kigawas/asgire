#!/usr/bin/env bash
# Fail if asgiref/__init__.py and pyproject.toml declare different versions.
set -euo pipefail

cd "$(dirname "$0")/.."

init_version=$(sed -n 's/^__version__[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' asgiref/__init__.py)
# Only look at the version key inside the [project] table.
pyproject_version=$(sed -n '/^\[project\]/,/^\[/ s/^version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' pyproject.toml)

if [ -z "$init_version" ]; then
  echo "version-check: could not find __version__ in asgiref/__init__.py" >&2
  exit 1
fi
if [ -z "$pyproject_version" ]; then
  echo "version-check: could not find version in [project] of pyproject.toml" >&2
  exit 1
fi
if [ "$init_version" != "$pyproject_version" ]; then
  echo "version-check: mismatch — pyproject.toml=$pyproject_version asgiref/__init__.py=$init_version" >&2
  exit 1
fi

echo "version-check: OK ($init_version)"
