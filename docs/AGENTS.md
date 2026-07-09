# Agent Usage Guide

`bb` is designed to be scriptable:

- Commands return exit code `0` on success and non-zero on failure.
- List/view commands use `--json` when structured output is needed.
- `bb doctor --json` is the first command an agent should run.
- Raw tokens are never printed by `auth status`. Use `bb auth token` only when
  a script explicitly needs the secret on stdout.

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
