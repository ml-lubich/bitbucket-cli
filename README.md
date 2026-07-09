# bb — Bitbucket CLI

A lightweight, gh-style command-line client for Bitbucket Cloud and Bitbucket
Data Center/Server with token
authentication, plain-text table output, and a `--json` flag on every
list/view command.

---

## Setup

### From source (development or local install)

```bash
git clone https://github.com/ml-lubich/bitbucket-cli
cd bitbucket-cli
./scripts/setup.sh        # installs uv if missing, then runs uv sync
UV_PROJECT_ENVIRONMENT=venv uv run bb --help
```

`scripts/setup.sh` is idempotent — safe to re-run after `git pull` or after
wiping the virtualenv. It creates `venv/` instead of `.venv/` so macOS hidden
file flags cannot break editable-install `.pth` loading.

### Global install (adds `bb` to PATH)

```bash
uv tool install .
bb --help
```

After the package is published to PyPI:

```bash
uv tool install bitbucket-cli
```

### Fallback only — if `uv` is not available

```bash
pip install -e .
```

---

## Authentication

By default, `bb` targets Bitbucket Cloud. For Bitbucket Data Center/Server, set
the web base URL first:

```bash
bb config set base_url https://bitbucket.polariswireless.com
```

`bb` resolves credentials in this order (first match wins):

| Priority | Source | Example |
|---|---|---|
| 1 | `BB_TOKEN` env var | `export BB_TOKEN="${YOUR_TOKEN}"` |
| 2 | `BITBUCKET_TOKEN` env var | `export BITBUCKET_TOKEN="${YOUR_TOKEN}"` |
| 3 | `BITBUCKET_AUTH_TOKEN` env var | `export BITBUCKET_AUTH_TOKEN="${YOUR_TOKEN}"` |
| 4 | Repo-local `.env` file | `BB_TOKEN="${YOUR_TOKEN}"` line in `.env` |
| 5 | OS keyring (macOS Keychain / Linux Secret Service) | — |
| 6 | `hosts.toml` fallback (mode 0600) | — |

**Interactive login** (paste once; stored globally until logout):

```bash
bb auth login                        # prompts securely; stores in OS keyring
bb auth login --token "${YOUR_TOKEN}"
echo "$TOKEN" | bb auth login --with-token --no-verify
bb auth status                       # verify stored credential
```

**Bitbucket Data Center/Server HTTP access tokens:** Tokens created from an
on-prem Bitbucket user access-token page, often with a `BBDC-...` prefix, use
Bearer auth against `https://your-bitbucket-host/rest/api/1.0`:

```bash
bb config set base_url https://bitbucket.polariswireless.com
bb auth login
bb doctor
```

`bb` also accepts on-prem repo URLs wherever a repo override is accepted, e.g.
`--repo https://bitbucket.polariswireless.com/scm/PVA/my-repo.git`.

**Bitbucket Cloud app passwords / Atlassian API tokens:** Atlassian API tokens (the `ATATT...`
format) require HTTP Basic auth with your Bitbucket account email as the
username. Pass `--username` to `bb auth login` or set `BITBUCKET_EMAIL` /
`BB_USERNAME` alongside the token env var.

**Never commit tokens.** Use environment variables or CI secret stores.

---

## Quick start

```bash
# Authenticate
UV_PROJECT_ENVIRONMENT=venv uv run bb auth login

# Pull requests
UV_PROJECT_ENVIRONMENT=venv uv run bb pr list
UV_PROJECT_ENVIRONMENT=venv uv run bb pr list --state MERGED --limit 10
UV_PROJECT_ENVIRONMENT=venv uv run bb pr create --title "Fix login bug"
UV_PROJECT_ENVIRONMENT=venv uv run bb pr merge 42 --merge-strategy squash --delete-branch

# Repositories
UV_PROJECT_ENVIRONMENT=venv uv run bb repo list --workspace myteam
UV_PROJECT_ENVIRONMENT=venv uv run bb repo clone myteam/myrepo
UV_PROJECT_ENVIRONMENT=venv uv run bb repo create --name new-service --workspace myteam

# Issues
UV_PROJECT_ENVIRONMENT=venv uv run bb issue list
UV_PROJECT_ENVIRONMENT=venv uv run bb issue create --title "Crash on startup" --kind bug --priority critical
UV_PROJECT_ENVIRONMENT=venv uv run bb issue close 7

# Pipelines
UV_PROJECT_ENVIRONMENT=venv uv run bb pipeline list
UV_PROJECT_ENVIRONMENT=venv uv run bb pipeline run --branch main
UV_PROJECT_ENVIRONMENT=venv uv run bb pipeline logs abc-uuid-1234
```

---

## Command reference

| Group | Subcommands |
|---|---|
| `auth` | `login`, `logout`, `status`, `token` |
| `pr` | `list`, `view`, `create`, `checkout`, `merge`, `close`, `reopen`, `edit`, `review`, `comment`, `diff`, `checks` |
| `repo` | `list`, `view`, `clone`, `create`, `fork`, `delete`, `sync`, `set-default` |
| `issue` | `list`, `view`, `create`, `edit`, `close`, `reopen`, `comment`, `delete` |
| `pipeline` | `list`, `run`, `view`, `steps`, `logs`, `stop` |
| `branch` | `list`, `create`, `delete` |
| `workspace` | `list`, `view`, `members` |
| `project` | `list`, `view`, `create` |
| `snippet` | `list`, `view`, `create`, `edit`, `delete` |
| `config` | `get`, `set` |
| `api` | (top-level command — raw authenticated API request) |
| `browse` | (top-level command — open repo in browser) |
| `doctor` | (top-level command — config/auth diagnostics) |
| `completion` | (top-level command — print shell completion script) |

Run `bb help`, `bb -h`, or `bb --help` for root help. Run
`bb help <group>`, `bb <group> -h`, or `bb <group> --help` for group flags.
Run `bb help <group> <subcommand>` or `bb <group> <subcommand> -h` for
per-subcommand flags.

Use `bb doctor --json` for agent-friendly setup/auth diagnostics.

---

## gh → bb mapping

| `gh` command | `bb` equivalent |
|---|---|
| `gh auth login` | `bb auth login` |
| `gh auth login --with-token` | `bb auth login --with-token` |
| `gh auth status` | `bb auth status` |
| `gh auth logout` | `bb auth logout` |
| `gh auth token` | `bb auth token` |
| `gh pr list` | `bb pr list` |
| `gh pr create` | `bb pr create` |
| `gh pr merge` | `bb pr merge <ID>` |
| `gh pr review --approve` | `bb pr review <ID> --approve` |
| `gh pr checks` | `bb pr checks <ID>` |
| `gh pr diff` | `bb pr diff <ID>` |
| `gh pr close` | `bb pr close <ID>` |
| `gh pr edit` | `bb pr edit <ID>` |
| `gh pr comment --body "…"` | `bb pr comment <ID> --body "…"` |
| `gh repo list` | `bb repo list` |
| `gh repo clone` | `bb repo clone workspace/slug` |
| `gh repo create` | `bb repo create --name myrepo` |
| `gh repo fork` | `bb repo fork workspace/slug` |
| `gh repo delete` | `bb repo delete workspace/slug` |
| `gh issue list` | `bb issue list` |
| `gh issue create` | `bb issue create --title "…"` |
| `gh issue close` | `bb issue close <ID>` |
| `gh run list` | `bb pipeline list` |
| `gh run view` | `bb pipeline view <UUID>` |
| `gh workflow run` | `bb pipeline run` |
| `gh api /repos/…` | `bb api /repositories/…` |
| `gh browse` | `bb browse` |
| `gh completion -s bash` | `bb completion bash` |

**Bitbucket-specific differences:**

- `bb pr reopen` is not supported — Bitbucket Cloud has no API endpoint to
  reopen a declined PR. The command exits 1 with a clear message.
- Pipeline references use UUIDs, not numeric run IDs.
- Bitbucket issue `--kind` values: `bug`, `enhancement`, `proposal`, `task`.

---

## Configuration

`bb` uses a documented precedence chain (changing order is a breaking change):

| Priority | Source |
|---|---|
| 1 (highest) | CLI arguments (`--repo`, `--workspace`, etc.) |
| 2 | Environment variables (`BB_REPO`, `BB_WORKSPACE`, `BB_EDITOR`, `BB_GIT_PROTOCOL`) |
| 3 | Project config (`bb.toml` at current working directory) |
| 4 | User config (`config.toml` via `platformdirs.user_config_dir("bb")`) |
| 5 (lowest) | Hardcoded defaults |

**Config keys** (valid for both `bb.toml` and `config.toml`):

| Key | Default | Description |
|---|---|---|
| `base_url` | `https://bitbucket.org` | Bitbucket web base URL; set to your Data Center host for on-prem |
| `git_protocol` | `https` | Clone protocol: `https` or `ssh` |
| `editor` | `""` | Editor for interactive prompts; falls back to `$EDITOR` |
| `default_repo` | `""` | Default repo as `workspace/slug` |
| `default_workspace` | `""` | Default workspace slug |

Read or write user config:

```bash
bb config get git_protocol
bb config get base_url
bb config set git_protocol ssh
bb config set base_url https://bitbucket.polariswireless.com
bb config set default_workspace myteam
```

Set a project-level default repo:

```bash
bb repo set-default myteam/myrepo   # writes default_repo to bb.toml at git root
```

**`BB_REPO` override:** set `BB_REPO=workspace/slug` to pin the target repo
in any environment (CI, scripts, or when running outside a git clone).

**`NO_COLOR`:** when set to any non-empty value, `rich` disables all terminal
color codes. Useful in CI or scripts that parse `bb` output.

---

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Testing](docs/TESTING.md)
- [Runbook](docs/RUNBOOK.md)
- [Agent usage](docs/AGENTS.md)
- [Publishing](docs/PUBLISHING.md)
- [Changelog](docs/CHANGELOG.md)

---

Copyright (c) 2026 Misha Lubich (ml-lubich) · MIT License
https://mishalubich.com · https://github.com/ml-lubich
