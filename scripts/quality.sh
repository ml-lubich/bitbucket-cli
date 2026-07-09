#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$REPO_ROOT"

export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-venv}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$REPO_ROOT/.uv-cache}"

uv run ruff check src tests
uv run mypy src/bb
uv run pytest --cov=bb --cov-report=term-missing --cov-report=json
