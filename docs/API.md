# API Reference

## Global flags (root)

| Flag | Description |
|---|---|
| `--version` | Print version string and exit |
| `-h, --help` | Show help for any command or subcommand |

### `bb help [COMMAND...]`

Show root help or help for a nested command path.

Examples:

```bash
bb help
bb help repo
bb help repo list
```

## Config precedence (contract — changing order is a breaking change)

1. CLI arguments (highest)
2. Environment variables
3. Project config (`bb.toml` at current working directory)
4. User config (`config.toml` via `platformdirs.user_config_dir("bb")`)
5. Hardcoded defaults (lowest)

## Config files

| File | Location (platform-resolved) | Format | Mode |
|---|---|---|---|
| User config | `platformdirs.user_config_dir("bb")/config.toml` | TOML | default |
| Token store | `platformdirs.user_config_dir("bb")/hosts.toml` | TOML | 0600 |
| Project config | `<cwd>/bb.toml` | TOML | default |

## Config keys

Valid keys for `bb config get/set` and both TOML config files:

| Key | Default | Description |
|---|---|---|
| `git_protocol` | `https` | Clone protocol: `https` or `ssh` |
| `editor` | `""` | Editor override; falls back to `$EDITOR` |
| `default_repo` | `""` | Default repo as `workspace/slug` |
| `default_workspace` | `""` | Default workspace slug |

## Environment variables

| Variable | Mapped key | Description |
|---|---|---|
| `BB_TOKEN` | — | Bitbucket API token or app password (token resolution, highest priority) |
| `BITBUCKET_TOKEN` | — | Alternative token env name |
| `BITBUCKET_AUTH_TOKEN` | — | Alternative token env name |
| `BB_REPO` | `default_repo` | Default repo `workspace/slug` |
| `BB_WORKSPACE` | `default_workspace` | Default workspace slug |
| `BB_EDITOR` | `editor` | Editor override |
| `BB_GIT_PROTOCOL` | `git_protocol` | Clone protocol override |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Any `BBError` subclass: `AuthError`, `ApiError`, `ContextError`, `ConfigError` |

`ApiError` carries the HTTP status code in the error message text (e.g. `bb: API 404: ...`).

---

## auth

### `bb auth login [OPTIONS]`

Store a Bitbucket access token. Prompts securely if `--token` is omitted.

| Flag | Description |
|---|---|
| `--token TEXT` | Token value; prompted securely if omitted |
| `--username TEXT` | Username for basic auth (optional) |
| `--no-verify` | Skip GET /user verification after storing token |

Writes `hosts.toml` with mode 0600 in the platformdirs user config dir.

### `bb auth logout`

Remove stored credentials from `hosts.toml`.

### `bb auth status`

Show current credential source and verify against the Bitbucket API. Exits 1 if not authenticated.

---

## pr

All `pr` subcommands accept `-R / --repo TEXT` to override git-remote context.

### `bb pr list [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo `workspace/slug` |
| `--state TEXT` | Filter: `OPEN` (default), `MERGED`, `DECLINED`, `SUPERSEDED` |
| `--limit INTEGER` | Maximum results (default 30) |
| `--reviewer TEXT` | Filter by reviewer username |
| `--json` | JSON output |

### `bb pr view <PR_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--json` | JSON output |
| `--web` | Open in browser instead of printing |

### `bb pr create [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--title TEXT` | PR title |
| `--body TEXT` | PR description |
| `--base TEXT` | Destination branch |
| `--head TEXT` | Source branch |
| `--draft` | Mark as draft |
| `--close-source-branch` | Delete source branch after merge |

### `bb pr checkout <PR_ID> [OPTIONS]`

Check out the source branch of a pull request locally.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |

### `bb pr merge <PR_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--merge-strategy TEXT` | `merge_commit` (default), `squash`, or `fast_forward` |
| `--delete-branch` | Delete source branch after merge |
| `--message TEXT` | Merge commit message |

### `bb pr close <PR_ID> [OPTIONS]`

Decline a pull request.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |

### `bb pr reopen <PR_ID> [OPTIONS]`

Not supported. Bitbucket Cloud API has no reopen endpoint. Exits 1 with a documented error.

### `bb pr edit <PR_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--title TEXT` | New title |
| `--body TEXT` | New description |
| `--base TEXT` | New destination branch |

### `bb pr review <PR_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--approve` | Approve the PR |
| `--request-changes` | Request changes |
| `--unapprove` | Remove approval |
| `--body TEXT` | Review comment body |

### `bb pr comment <PR_ID> [OPTIONS]`

| Flag | Required | Description |
|---|---|---|
| `-R, --repo TEXT` | no | Target repo |
| `--body TEXT` | yes | Comment body |

### `bb pr diff <PR_ID> [OPTIONS]`

Print the unified diff of a pull request.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |

### `bb pr checks <PR_ID> [OPTIONS]`

Show build statuses for a pull request's source commit.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |

---

## repo

### `bb repo list [OPTIONS]`

| Flag | Description |
|---|---|
| `-w, --workspace TEXT` | Workspace slug |
| `--limit INTEGER` | Maximum results (default 30) |
| `--role TEXT` | Filter by role |
| `--json` | JSON output |

### `bb repo view [workspace/slug] [OPTIONS]`

Show repository details. Uses git-remote context if not specified.

| Flag | Description |
|---|---|
| `--web` | Open in browser instead of printing |

### `bb repo clone <workspace/slug> [DIRECTORY]`

Clone a repository. Respects `git_protocol` config key (`https` or `ssh`).

### `bb repo create [OPTIONS]`

| Flag | Required | Description |
|---|---|---|
| `--name TEXT` | yes | Repository slug |
| `-w, --workspace TEXT` | no | Target workspace |
| `--private` / `--public` | no | Visibility (default: private) |
| `--description TEXT` | no | Repository description |
| `--project TEXT` | no | Project key to associate |

### `bb repo fork <workspace/slug> [OPTIONS]`

Fork a repository.

| Flag | Description |
|---|---|
| `-w, --workspace TEXT` | Target workspace for the fork |

### `bb repo delete <workspace/slug> [OPTIONS]`

Delete a repository. Prompts for confirmation unless `--yes`.

| Flag | Description |
|---|---|
| `-y, --yes` | Skip confirmation prompt |

### `bb repo sync`

Sync a forked repository with its upstream parent (git fetch + merge).

### `bb repo set-default <workspace/slug>`

Write `default_repo` into `bb.toml` at the git repo root.

---

## issue

Requires issue tracker enabled for the repository. Commands exit 1 with a
clear message if the tracker is disabled (Bitbucket API returns 404).

All `issue` subcommands accept `-R / --repo TEXT` (`workspace/slug`).

### `bb issue list [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo `workspace/slug` |
| `--state TEXT` | `open` (default), `new`, `resolved`, `on hold`, `invalid`, `duplicate`, `wontfix`, `closed` |
| `--limit INTEGER` | Max results (default 30) |
| `--json` | JSON output |

### `bb issue view <ISSUE_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--json` | JSON output |

### `bb issue create [OPTIONS]`

| Flag | Required | Description |
|---|---|---|
| `-R, --repo TEXT` | no | Target repo |
| `--title TEXT` | yes | Issue title |
| `--body TEXT` | no | Issue body |
| `--kind TEXT` | no | `bug` (default), `enhancement`, `proposal`, `task` |
| `--priority TEXT` | no | `major` (default), `trivial`, `minor`, `critical`, `blocker` |

### `bb issue edit <ISSUE_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--title TEXT` | New title |
| `--body TEXT` | New description |
| `--kind TEXT` | New kind |
| `--priority TEXT` | New priority |

### `bb issue close <ISSUE_ID> [OPTIONS]`

Set issue state to `resolved`.

### `bb issue reopen <ISSUE_ID> [OPTIONS]`

Set issue state to `open`.

### `bb issue comment <ISSUE_ID> [OPTIONS]`

| Flag | Required | Description |
|---|---|---|
| `-R, --repo TEXT` | no | Target repo |
| `--body TEXT` | yes | Comment body |

### `bb issue delete <ISSUE_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `-y, --yes` | Skip confirmation prompt |

---

## pipeline

All `pipeline` subcommands accept `-R / --repo TEXT` (`workspace/slug`).

### `bb pipeline list [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--limit INTEGER` | Max results (default 20) |
| `--json` | JSON output |

### `bb pipeline run [OPTIONS]`

Trigger a pipeline run.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--branch TEXT` | Branch to run (default: current branch) |

### `bb pipeline view <UUID> [OPTIONS]`

Show pipeline details.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--json` | JSON output |

### `bb pipeline steps <UUID> [OPTIONS]`

List pipeline steps.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--json` | JSON output |

### `bb pipeline logs <UUID> [OPTIONS]`

Print pipeline step logs.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--step TEXT` | Step UUID (omit to print all steps) |

### `bb pipeline stop <UUID> [OPTIONS]`

Stop a running pipeline.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |

---

## branch

All `branch` subcommands accept `-R / --repo TEXT`.

### `bb branch list [OPTIONS]`

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--limit INTEGER` | Max results (default 30) |
| `--json` | JSON output |

### `bb branch create <NAME> [OPTIONS]`

Create a branch.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `--from TEXT` | Source commit or branch |

### `bb branch delete <NAME> [OPTIONS]`

Delete a branch.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo |
| `-y, --yes` | Skip confirmation prompt |

---

## workspace

### `bb workspace list [OPTIONS]`

List all workspaces the authenticated user belongs to.

| Flag | Description |
|---|---|
| `--json` | JSON output |

### `bb workspace view <SLUG>`

Show details for a workspace.

### `bb workspace members <SLUG> [OPTIONS]`

List members of a workspace.

| Flag | Description |
|---|---|
| `--json` | JSON output |

---

## project

### `bb project list [OPTIONS]`

List projects in a workspace.

| Flag | Description |
|---|---|
| `-w, --workspace TEXT` | Workspace slug |
| `--json` | JSON output |

### `bb project view <KEY> [OPTIONS]`

Show project details by project key.

| Flag | Description |
|---|---|
| `-w, --workspace TEXT` | Workspace slug |

### `bb project create [OPTIONS]`

| Flag | Required | Description |
|---|---|---|
| `--key TEXT` | yes | Project key (e.g. `PROJ`) |
| `--name TEXT` | yes | Project name |
| `-w, --workspace TEXT` | no | Workspace slug |
| `--private` / `--public` | no | Visibility (default: private) |
| `--description TEXT` | no | Project description |

---

## snippet

### `bb snippet list [OPTIONS]`

| Flag | Description |
|---|---|
| `--role TEXT` | `owner` (default), `contributor`, `member` |
| `--json` | JSON output |

### `bb snippet view <WORKSPACE> <SNIP_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `--raw` | Print raw file content |
| `--file TEXT` | File name within the snippet (used with `--raw`) |

### `bb snippet create [OPTIONS]`

| Flag | Required | Description |
|---|---|---|
| `--title TEXT` | yes | Snippet title |
| `--file TEXT` | yes | Path to file to upload |
| `--private` / `--public` | no | Visibility (default: private) |

### `bb snippet edit <WORKSPACE> <SNIP_ID> [OPTIONS]`

Edit a snippet (title only).

| Flag | Description |
|---|---|
| `--title TEXT` | New title |

### `bb snippet delete <WORKSPACE> <SNIP_ID> [OPTIONS]`

| Flag | Description |
|---|---|
| `-y, --yes` | Skip confirmation prompt |

---

## api

### `bb api [ENDPOINT] [OPTIONS]`

Make a raw authenticated request to the Bitbucket Cloud API 2.0 and print JSON.

| Argument / Flag | Description |
|---|---|
| `ENDPOINT` | API path, e.g. `/2.0/repositories/myworkspace/my-repo` |
| `-X, --method TEXT` | HTTP method: `GET` (default), `POST`, `PUT`, `DELETE`, `PATCH` |
| `-f, --field TEXT` | `key=value` body field; repeatable |
| `--paginate` | Follow `next` page links and aggregate results |
| `--input TEXT` | JSON body from file |

Subcommand alias: `bb api request` is equivalent to `bb api`.

---

## browse

### `bb browse [OPTIONS]`

Open the current repository in the system browser.

| Flag | Description |
|---|---|
| `-r, --repo TEXT` | workspace/slug override |
| `-b, --branch TEXT` | Open branch view |
| `--no-open` | Print URL only; do not open browser |

---

## config

### `bb config get <KEY>`

Print the resolved value for a config key from the user config file.

### `bb config set <KEY> <VALUE>`

Write a key-value pair to the user config file (`config.toml` via platformdirs).

Valid keys: `git_protocol`, `editor`, `default_repo`, `default_workspace`.

---

## completion

### `bb completion <SHELL>`

Print shell completion script for the given shell.

Supported shells: `bash`, `zsh`, `fish`, `powershell`.

Source the output in your shell profile to enable tab completion:

```bash
# zsh
eval "$(bb completion zsh)"

# bash
eval "$(bb completion bash)"

# fish
bb completion fish | source

# PowerShell
Invoke-Expression (bb completion powershell)
```
