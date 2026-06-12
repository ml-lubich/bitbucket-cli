#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$REPO_ROOT"

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) echo "Unix only (macOS / Linux)" >&2; exit 1 ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  hash -r 2>/dev/null || true
fi

uv sync
echo "Setup complete."
