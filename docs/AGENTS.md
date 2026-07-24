# Agent Usage Guide

`bb` is designed to be scriptable:

- Commands return exit code `0` on success and non-zero on failure.
- List/view commands use `--json` when structured output is needed.
- `bb doctor --json` is the first command an agent should run.
- Raw tokens are never printed by `auth status`. Use `bb auth token` only when
  a script explicitly needs the secret on stdout.

## Install (agents)

Prefer one install path so `bb` on PATH is unambiguous:

```bash
brew install ml-lubich/tap/bitbucket-client
bb --version   # expect 0.3.1+
```

PyPI alternative: `uv tool install bitbucket-client` (same `bb` console script).
Avoid mixing Homebrew, `uv tool`, and a repo `venv` symlink for `bb` — that
shadows the intended binary.

## Bootstrap

```bash
bb config set base_url https://bitbucket.polariswireless.com
bb auth login
bb doctor --json
```

For non-interactive environments, provide secrets through environment variables
or stdin:

```bash
export BB_BASE_URL=https://bitbucket.polariswireless.com
export BB_TOKEN="${BITBUCKET_HTTP_ACCESS_TOKEN}"
bb doctor --json
# or:
printf '%s' "$BITBUCKET_HTTP_ACCESS_TOKEN" | bb auth login --with-token --no-verify
```

## MCP (coding agents)

`bb mcp serve` is a **read-only** stdio MCP server (JSON-RPC 2.0). Tools are
GET-only (`whoami`, `repo_*`, `pr_*`, `issue_list`, `pipeline_list`, `api_get`)
and reuse the same auth / Cloud↔Data Center path mapping as the CLI.

```bash
# Claude Code
claude mcp add bitbucket -- bb mcp serve
```

Cursor (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "bitbucket": {
      "command": "bb",
      "args": ["mcp", "serve"]
    }
  }
}
```

Smoke:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' | bb mcp serve
```

## Repo Targeting

Use `PROJECT/repo` or a full Bitbucket URL:

```bash
bb pr list --repo PVA/radio --json
bb pr list --repo https://bitbucket.polariswireless.com/scm/PVA/radio.git --json
```

## Raw API

`bb api` accepts Cloud/Data Center-relative paths. With the Polaris base URL,
Cloud-shaped repo paths are translated to Data Center REST paths:

```bash
bb api /projects
bb api /repositories/PVA/radio
```

## Error Handling

API errors include:

- HTTP status code
- method/path when available
- a short remediation hint for common statuses

Agents should surface the full error string to the user and avoid retrying 401,
403, and 404 without changing credentials or the requested repo path.
