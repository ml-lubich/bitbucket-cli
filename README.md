# bb — Bitbucket CLI

`bb` is a fast, `gh`-style command line for **Bitbucket Cloud** and **Bitbucket
Data Center/Server**. It gives you pull requests, repos, issues, pipelines, and
more from your terminal — with human-readable tables by default and a `--json`
flag on every list/view command for scripts and agents.

```bash
bb pr list
bb pr create --title "Fix login bug"
bb repo clone myteam/myrepo
```

---

## Install

The recommended install puts a `bb` command on your `PATH` — no prefixes, no
activation:

```bash
uv tool install .          # from a clone
# or, once published to PyPI:
uv tool install bitbucket-bb
bb --help
```

> The PyPI package is `bitbucket-bb` (the name `bitbucket-cli` was already taken
> by an unrelated project). The installed command is always `bb`.

No `uv`? `pip install -e .` works too.

<details>
<summary>Developing on <code>bb</code> itself</summary>

To run from a clone **without** installing globally:

```bash
git clone https://github.com/ml-lubich/bitbucket-cli
cd bitbucket-cli
./scripts/setup.sh                              # installs uv if missing, then syncs
UV_PROJECT_ENVIRONMENT=venv uv run bb --help    # run inside the project venv
```

`setup.sh` is idempotent — re-run it anytime. It uses `venv/` (not `.venv/`) so
macOS hidden-file flags can't break the editable install. The
`UV_PROJECT_ENVIRONMENT=venv uv run` prefix is **only** for this run-from-source
workflow; once you `uv tool install .`, just use `bb`.

</details>

---

## Authenticate

`bb` targets Bitbucket Cloud by default. On Bitbucket Cloud in an interactive
terminal, just log in through your browser:

```bash
bb auth login          # opens your browser for Atlassian SSO (OAuth 2.0)
bb auth status         # confirm you're logged in
```

`bb` stores an access token plus a rotating refresh token in your OS keyring and
refreshes them automatically — you won't log in again until the refresh token is
revoked or expires. See [docs/AUTH.md](docs/AUTH.md) for the full flow and how to
use your own OAuth consumer.

**Token login** (Data Center, CI, or any non-interactive shell):

```bash
bb config set base_url https://bitbucket.example.com   # Data Center only
bb auth login --token "$YOUR_TOKEN"
echo "$YOUR_TOKEN" | bb auth login --with-token        # from stdin
```

- **Data Center HTTP access tokens** (often `BBDC-…`) use Bearer auth against
  `https://your-host/rest/api/1.0`.
- **Atlassian API tokens** (`ATATT…`) use Basic auth — pass `--username <email>`
  or set `BITBUCKET_EMAIL` / `BB_USERNAME`.

`bb` also reads a token from the environment (first match wins): `BB_TOKEN`,
`BITBUCKET_TOKEN`, `BITBUCKET_AUTH_TOKEN`, or a `BB_TOKEN=…` line in a repo-local
`.env`. **Never commit tokens** — use env vars or your CI secret store.

Other auth commands: `bb auth refresh` (force refresh), `bb auth setup-git`
(print `git -c` flags for authenticated HTTPS), `bb auth logout`.

---

## Quick start

```bash
# Pull requests
bb pr list
bb pr list --state MERGED --limit 10
bb pr create --title "Fix login bug"
bb pr merge 42 --merge-strategy squash --delete-branch

# Repositories
bb repo list --workspace myteam
bb repo clone myteam/myrepo
bb repo create --name new-service --workspace myteam

# Issues
bb issue list
bb issue create --title "Crash on startup" --kind bug --priority critical
bb issue close 7

# Pipelines
bb pipeline list
bb pipeline run --branch main
bb pipeline logs abc-uuid-1234
bb pipeline variable create --key API_KEY --value secret --secured

# Search & status
bb search repos myservice --workspace myteam
bb search code "TODO" --workspace myteam
bb status            # you + PRs awaiting your review
```

Add `--json` to any list/view command for machine-readable output, and
`bb doctor --json` for agent-friendly setup/auth diagnostics.

---

## Commands

| Group | Subcommands |
|---|---|
| `auth` | `login` (browser OAuth or token), `logout`, `status`, `token`, `refresh`, `setup-git` |
| `pr` | `list`, `view` (`--comments`), `create`, `checkout`, `merge`, `close`, `reopen`, `edit`, `review`, `comment`, `diff`, `checks`, `status` |
| `repo` | `list`, `view`, `clone`, `create`, `fork`, `delete`, `sync`, `edit`, `set-default` |
| `issue` | `list`, `view`, `create`, `edit`, `close`, `reopen`, `comment`, `delete`, `status` |
| `pipeline` | `list`, `run`, `view`, `steps`, `logs`, `stop`, `variable` (`list`, `create`, `delete`) |
| `branch` | `list`, `create`, `delete` |
| `workspace` | `list`, `view`, `members` |
| `project` | `list`, `view`, `create` |
| `snippet` | `list`, `view`, `create`, `edit`, `delete` |
| `search` | `repos`, `code` |
| `config` | `get`, `set` |
| `api` | raw authenticated API request |
| `browse` | open the repo in your browser |
| `doctor` | config/auth diagnostics |
| `status` | current user + PRs awaiting your review |
| `completion` | print a shell completion script |

Help is available at every level: `bb --help`, `bb <group> --help`,
`bb <group> <subcommand> --help` (or `-h`).

---

## Coming from `gh`?

`bb` mirrors GitHub CLI ergonomics where Bitbucket has an equivalent:

| `gh` | `bb` |
|---|---|
| `gh auth login` | `bb auth login` |
| `gh auth status` / `logout` / `token` / `refresh` / `setup-git` | same on `bb auth` |
| `gh pr list` / `create` / `status` | same on `bb pr` |
| `gh pr merge` / `review --approve` / `checks` / `diff` / `close` / `edit` | `bb pr <cmd> <ID>` |
| `gh pr comment --body "…"` | `bb pr comment <ID> --body "…"` |
| `gh pr view --comments` | `bb pr view <ID> --comments` |
| `gh repo list` / `create` / `edit` | same on `bb repo` |
| `gh repo clone` / `fork` / `delete` | `bb repo <cmd> workspace/slug` |
| `gh issue list` / `create` / `close` / `status` | same on `bb issue` |
| `gh run list` / `view` | `bb pipeline list` / `view <UUID>` |
| `gh workflow run` | `bb pipeline run` |
| `gh secret set` / `variable set` | `bb pipeline variable create --key K --value V [--secured]` |
| `gh api /repos/…` | `bb api /repositories/…` |
| `gh browse` / `status` / `search repos` / `search code` | same on `bb` |
| `gh completion -s bash` | `bb completion bash` |

**Where Bitbucket differs from GitHub:**

- No `bb pr reopen` — Bitbucket Cloud can't reopen a declined PR (the command
  exits with a clear message).
- No `bb pr ready`, `bb repo rename`, or `bb repo archive` — no Cloud API for them.
- No `label` or `release` commands — Bitbucket Cloud has no analog.
- Pipelines are referenced by UUID, not a numeric run ID.
- Issue `--kind` values: `bug`, `enhancement`, `proposal`, `task`.
- Browser login is Cloud-only; Data Center always uses `--with-token`.

---

## Configuration

Settings resolve top-down (first match wins):

| Priority | Source |
|---|---|
| 1 | CLI flags (`--repo`, `--workspace`, …) |
| 2 | Environment (`BB_REPO`, `BB_WORKSPACE`, `BB_EDITOR`, `BB_GIT_PROTOCOL`, `BB_OAUTH_CLIENT_ID`, `BB_OAUTH_CLIENT_SECRET`) |
| 3 | Project config — `bb.toml` in the current directory |
| 4 | User config — `config.toml` (`platformdirs.user_config_dir("bb")`) |
| 5 | Built-in defaults |

Keys (valid in both `bb.toml` and `config.toml`):

| Key | Default | Description |
|---|---|---|
| `base_url` | `https://bitbucket.org` | Bitbucket web base URL; set to your host for Data Center |
| `git_protocol` | `https` | Clone protocol: `https` or `ssh` |
| `editor` | `""` | Editor for prompts; falls back to `$EDITOR` |
| `default_repo` | `""` | Default repo as `workspace/slug` |
| `default_workspace` | `""` | Default workspace slug |
| `oauth_client_id` / `oauth_client_secret` | `""` | Your own OAuth consumer for browser login (see [docs/AUTH.md](docs/AUTH.md)) |

```bash
bb config set base_url https://bitbucket.example.com
bb config set default_workspace myteam
bb config set git_protocol ssh
bb repo set-default myteam/myrepo    # writes default_repo to bb.toml at the git root
```

Set `BB_REPO=workspace/slug` to pin the target repo anywhere (CI, scripts, or
outside a clone). Set `NO_COLOR` to disable colored output.

---

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Authentication](docs/AUTH.md) — OAuth flow, refresh model, security notes
- [API reference](docs/API.md)
- [Testing](docs/TESTING.md) · [Runbook](docs/RUNBOOK.md) · [Agent usage](docs/AGENTS.md)
- [Publishing](docs/PUBLISHING.md) · [Changelog](docs/CHANGELOG.md)

---

MIT License · Copyright (c) 2026 Misha Lubich ([ml-lubich](https://github.com/ml-lubich)) · [mishalubich.com](https://mishalubich.com)
