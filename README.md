# bb — Bitbucket Cloud CLI

bb is a lightweight, gh-style command-line client for Bitbucket Cloud with token authentication.

## Setup (macOS / Linux)

```bash
./scripts/setup.sh
```

This installs `uv` if missing, then runs `uv sync` from the repo root. Safe to re-run after `git pull`.

**Fallback only** — if `uv` is unavailable and you cannot run the script:

```bash
pip install -e .
```

Label this "fallback only"; the documented and supported path is `./scripts/setup.sh`.

## Authentication

Log in by pasting a Bitbucket API token or app password:

```bash
uv run bb auth login --token ${BB_TOKEN}
```

**Token sources** (highest to lowest priority):

| Source | Description |
|---|---|
| `BB_TOKEN` env var | Highest priority — overrides everything |
| `BITBUCKET_TOKEN` env var | Alternative env name |
| `BITBUCKET_AUTH_TOKEN` env var | Alternative env name |
| Repo-local `.env` file | `BB_TOKEN=...` line; parsed at startup; never echoed |
| `hosts.toml` (platformdirs) | Written by `bb auth login`; mode 0600 |

Tokens are stored in the platform user-config directory (e.g. `~/.config/bb/hosts.toml` on Linux, `~/Library/Application Support/bb/hosts.toml` on macOS) with permissions 0600.

**NEVER commit tokens.** Use `${BB_TOKEN}` placeholders in scripts and CI secrets.

Create tokens at: Bitbucket → Personal settings → API tokens (or App passwords).
Required scopes depend on commands used: `repository`, `pullrequest`, `pipeline`, `issue`, `snippet`, `project`, `workspace:read`.

## Usage

### Command groups

| Group | Description |
|---|---|
| `auth` | Authenticate and manage credentials |
| `pr` | Pull request lifecycle |
| `repo` | Repository management |
| `issue` | Issue tracker |
| `pipeline` | CI/CD pipelines |
| `branch` | Branch management |
| `workspace` | Workspace listing and members |
| `project` | Workspace projects |
| `snippet` | Bitbucket snippets |
| `api` | Raw authenticated API requests |
| `config` | Read and write local/user config |
| `browse` | Open resource URLs in browser |
| `completion` | Shell completion scripts |

### Examples

```bash
# List open pull requests for the current repo
uv run bb pr list

# Create a pull request
uv run bb pr create --title "Fix login redirect" --body "Resolves #42"

# Merge a pull request (squash)
uv run bb pr merge 17 --squash

# Review a pull request
uv run bb pr review 17 --approve

# List pipelines
uv run bb pipeline list

# Stream logs for a pipeline step
uv run bb pipeline logs abc123 --step 0

# Create an issue
uv run bb issue create --title "Button misaligned on mobile" --body "See screenshot"

# Clone a repo (uses git_protocol from config, default https)
uv run bb repo clone myworkspace/my-repo

# Raw API call
uv run bb api /2.0/repositories/myworkspace/my-repo

# Output as JSON
uv run bb pr list --json
```

## gh → bb mapping

| gh command | bb equivalent |
|---|---|
| `gh auth login` | `bb auth login` |
| `gh pr list` | `bb pr list` |
| `gh pr create` | `bb pr create` |
| `gh pr merge` | `bb pr merge` |
| `gh repo clone` | `bb repo clone` |
| `gh issue create` | `bb issue create` |
| `gh run list` | `bb pipeline list` |
| `gh api /repos/...` | `bb api /2.0/repositories/...` |

Note: Bitbucket does not support `pr reopen` — `bb pr reopen` surfaces a documented error.

## 4-Eyes Verification

- [ ] Run `./scripts/setup.sh` — exits 0, prints "Setup complete."
- [ ] Run `uv run pytest` — all tests pass, exit 0
- [ ] Run `uv run bb --help` — command groups listed, no traceback
- [ ] Run `uv run bb auth status` with no token configured — prints clean "Not logged in" message, exits 1
- [ ] Review all output: no token value (raw string) appears anywhere — only masked or absent

## Config Keys

### Precedence (highest wins)

1. CLI arguments (`--repo`, `--json`, etc.)
2. Environment variables (`BB_TOKEN`, `BB_REPO`, `BB_WORKSPACE`, `BB_EDITOR`)
3. Project config (`bb.toml` at repo root or any ancestor up to `.git`)
4. User config (`config.toml` via platformdirs user config dir)
5. Hardcoded defaults

Changing this order is a breaking change — documented here as the contract.

### Config file keys

| Key | Default | Description |
|---|---|---|
| `git_protocol` | `https` | Clone protocol: `https` or `ssh` |
| `editor` | `""` (inherits `$EDITOR`) | Editor for compose flows |
| `default_workspace` | `""` | Default Bitbucket workspace slug |

Set a key:

```bash
uv run bb config set git_protocol ssh
uv run bb config set default_workspace myworkspace
```

### Environment variables

| Variable | Description |
|---|---|
| `BB_TOKEN` | Bitbucket API token or app password |
| `BITBUCKET_TOKEN` | Alternative token env name |
| `BITBUCKET_AUTH_TOKEN` | Alternative token env name |
| `BB_REPO` | Default repo in `workspace/slug` form |
| `BB_WORKSPACE` | Default workspace slug |
| `BB_EDITOR` | Editor override (falls back to `$EDITOR`) |

## Links

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Testing](docs/TESTING.md)
- [Runbook](docs/RUNBOOK.md)
- [Changelog](docs/CHANGELOG.md)

---

Copyright (c) 2026 Misha Lubich (ml-lubich) · MIT License
https://mishalubich.com · https://github.com/ml-lubich
