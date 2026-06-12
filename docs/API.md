# API Reference

## Global flags

| Flag | Short | Description |
|---|---|---|
| `--repo` | `-R` | Target repo as `workspace/slug`; overrides git-remote detection |
| `--json` | | Emit raw JSON instead of formatted table |
| `--version` | | Print version and exit |
| `--help` | | Show help for any command or subcommand |

## Config precedence (contract — changing order is breaking)

1. CLI arguments (highest)
2. Environment variables (`BB_TOKEN`, `BB_REPO`, `BB_WORKSPACE`, `BB_EDITOR`)
3. Project config (`bb.toml` at repo root or nearest ancestor with `.git`)
4. User config (`config.toml` in platformdirs user config dir)
5. Hardcoded defaults (lowest)

## Config files

| File | Location | Format |
|---|---|---|
| User config | `platformdirs.user_config_dir("bb")/config.toml` | TOML |
| Token store | `platformdirs.user_config_dir("bb")/hosts.toml` | TOML, mode 0600 |
| Project config | `<repo-root>/bb.toml` | TOML |

## Environment variables

| Variable | Description |
|---|---|
| `BB_TOKEN` | Bitbucket API token or app password (highest priority) |
| `BITBUCKET_TOKEN` | Alternative token name |
| `BITBUCKET_AUTH_TOKEN` | Alternative token name |
| `BB_REPO` | Default repo `workspace/slug` |
| `BB_WORKSPACE` | Default workspace slug |
| `BB_EDITOR` | Editor override; falls back to `$EDITOR` |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Any `BBError` subclass: auth failure, API error, context error, config error |

`ApiError` carries the HTTP status code in the error message text (e.g. `bb: API 404: ...`).

---

## auth

### `bb auth login`

Authenticate with a Bitbucket token or app password.

| Flag | Description |
|---|---|
| `--token TEXT` | Token value to store (required) |
| `--username TEXT` | Bitbucket username (optional; stored alongside token) |

Writes `hosts.toml` with mode 0600 in the platformdirs user config dir.

### `bb auth logout`

Remove stored credentials from `hosts.toml`.

### `bb auth status`

Show current authentication state. Prints credential source and masked token. Exits 1 if not authenticated.

---

## pr

### `bb pr list`

List pull requests for the current or specified repo.

| Flag | Description |
|---|---|
| `-R, --repo TEXT` | Target repo `workspace/slug` |
| `--state TEXT` | Filter: `OPEN` (default), `MERGED`, `DECLINED`, `SUPERSEDED` |
| `--limit INT` | Maximum results (default 50) |
| `--json` | JSON output |

### `bb pr view <id>`

Show pull request details.

| Flag | Description |
|---|---|
| `--json` | JSON output |

### `bb pr create`

Create a new pull request.

| Flag | Description |
|---|---|
| `--title TEXT` | PR title (required) |
| `--body TEXT` | PR description |
| `--source TEXT` | Source branch (default: current branch) |
| `--dest TEXT` | Destination branch (default: repo default branch) |
| `--reviewer TEXT` | Reviewer username; repeatable |
| `--draft` | Mark as draft |

### `bb pr checkout <id>`

Check out the source branch of a pull request locally.

### `bb pr merge <id>`

Merge a pull request.

| Flag | Description |
|---|---|
| `--squash` | Squash commits |
| `--ff` | Fast-forward merge |
| `--message TEXT` | Merge commit message |
| `--delete-branch` | Delete source branch after merge |

### `bb pr close <id>`

Decline (close) a pull request.

### `bb pr reopen <id>`

Not supported. Bitbucket Cloud API has no reopen endpoint. Exits 1 with a clear error.

### `bb pr edit <id>`

Edit pull request title or description.

| Flag | Description |
|---|---|
| `--title TEXT` | New title |
| `--body TEXT` | New description |

### `bb pr review <id>`

Submit a review decision.

| Flag | Description |
|---|---|
| `--approve` | Approve the PR |
| `--request-changes` | Request changes |
| `--comment TEXT` | Comment text |

### `bb pr comment <id>`

Add a comment to a pull request.

| Flag | Description |
|---|---|
| `--body TEXT` | Comment body (required) |

### `bb pr diff <id>`

Print the unified diff of a pull request.

### `bb pr checks <id>`

List build status checks for a pull request's source commit.

---

## repo

### `bb repo list`

List repositories for a workspace.

| Flag | Description |
|---|---|
| `--workspace TEXT` | Workspace slug (default: config or git-remote) |
| `--limit INT` | Maximum results (default 50) |
| `--json` | JSON output |

### `bb repo view [workspace/slug]`

Show repository details. Uses git-remote context if not specified.

### `bb repo clone <workspace/slug>`

Clone a repository. Respects `git_protocol` config key (`https` or `ssh`).

### `bb repo create`

Create a new repository.

| Flag | Description |
|---|---|
| `--name TEXT` | Repository slug (required) |
| `--workspace TEXT` | Target workspace |
| `--private` | Make private (default true) |
| `--description TEXT` | Repository description |

### `bb repo fork [workspace/slug]`

Fork a repository into the authenticated user's workspace.

### `bb repo delete [workspace/slug]`

Delete a repository. Prompts for confirmation.

### `bb repo sync`

Sync a forked repository with its upstream.

### `bb repo set-default <workspace/slug>`

Write `default_workspace` and the repo slug into the project `bb.toml`.

---

## issue

Requires issue tracker enabled for the repository. Commands exit 1 with a clear message if the tracker is disabled (Bitbucket API returns 404 on the issues endpoint).

### `bb issue list`

| Flag | Description |
|---|---|
| `--state TEXT` | `new`, `open`, `resolved`, `on hold`, `invalid`, `duplicate`, `wontfix`, `closed` |
| `--limit INT` | Maximum results (default 50) |
| `--json` | JSON output |

### `bb issue view <id>`

Show issue details.

### `bb issue create`

| Flag | Description |
|---|---|
| `--title TEXT` | Issue title (required) |
| `--body TEXT` | Issue description |
| `--kind TEXT` | `bug`, `enhancement`, `proposal`, `task` |
| `--priority TEXT` | `trivial`, `minor`, `major`, `critical`, `blocker` |

### `bb issue edit <id>`

Edit issue fields.

| Flag | Description |
|---|---|
| `--title TEXT` | New title |
| `--body TEXT` | New description |
| `--state TEXT` | New state |

### `bb issue close <id>`

Set issue state to `resolved`.

### `bb issue reopen <id>`

Set issue state to `open`.

### `bb issue comment <id>`

Add a comment.

| Flag | Description |
|---|---|
| `--body TEXT` | Comment body (required) |

### `bb issue delete <id>`

Delete an issue. Prompts for confirmation.

---

## pipeline

### `bb pipeline list`

List pipeline runs.

| Flag | Description |
|---|---|
| `--branch TEXT` | Filter by branch |
| `--limit INT` | Maximum results (default 20) |
| `--json` | JSON output |

### `bb pipeline run`

Trigger a pipeline.

| Flag | Description |
|---|---|
| `--branch TEXT` | Branch to run on (default: current branch) |
| `--pattern TEXT` | Custom pipeline pattern name |

### `bb pipeline view <uuid>`

Show pipeline details. UUID may be passed with or without braces.

### `bb pipeline steps <uuid>`

List steps for a pipeline run.

### `bb pipeline logs <uuid>`

Stream or print logs for a pipeline.

| Flag | Description |
|---|---|
| `--step INT` | Step index (default 0) |

### `bb pipeline stop <uuid>`

Stop a running pipeline.

---

## branch

### `bb branch list`

List branches.

| Flag | Description |
|---|---|
| `--limit INT` | Maximum results (default 50) |
| `--json` | JSON output |

### `bb branch create <name>`

Create a branch from the current or specified source.

| Flag | Description |
|---|---|
| `--source TEXT` | Source commit or branch (default: default branch) |

### `bb branch delete <name>`

Delete a branch.

| Flag | Description |
|---|---|
| `--force` | Force delete |

---

## workspace

### `bb workspace list`

List workspaces the authenticated user belongs to.

### `bb workspace view <slug>`

Show workspace details.

### `bb workspace members <slug>`

List workspace members.

---

## project

### `bb project list`

List projects in a workspace.

| Flag | Description |
|---|---|
| `--workspace TEXT` | Workspace slug |

### `bb project view <key>`

Show project details by project key.

### `bb project create`

Create a project in a workspace.

| Flag | Description |
|---|---|
| `--workspace TEXT` | Workspace slug (required) |
| `--name TEXT` | Project name (required) |
| `--key TEXT` | Project key, e.g. `PROJ` (required) |
| `--private` | Make private (default true) |

---

## snippet

### `bb snippet list`

List snippets for the authenticated user or a workspace.

### `bb snippet view <id>`

Show snippet content and metadata.

### `bb snippet create`

Create a snippet.

| Flag | Description |
|---|---|
| `--title TEXT` | Snippet title |
| `--file PATH` | File to upload (repeatable) |
| `--private` | Make private |

### `bb snippet edit <id>`

Update snippet files.

| Flag | Description |
|---|---|
| `--file PATH` | Replacement file |

### `bb snippet delete <id>`

Delete a snippet.

---

## api

### `bb api <endpoint>`

Send an authenticated request to the Bitbucket Cloud API.

| Flag | Description |
|---|---|
| `--method TEXT` | HTTP method: `GET` (default), `POST`, `PATCH`, `PUT`, `DELETE` |
| `--field KEY=VALUE` | JSON body field; repeatable |
| `--input FILE` | Read JSON body from file |

Endpoint should be a full Bitbucket API 2.0 path, e.g. `/2.0/repositories/myworkspace/my-repo`.
Output is raw JSON.

---

## config

### `bb config get <key>`

Print the resolved value for a config key.

### `bb config set <key> <value>`

Write a key-value pair to the user config file.

Valid keys: `git_protocol`, `editor`, `default_workspace`.

---

## browse

### `bb browse`

Open the current repository in the system browser.

| Flag | Description |
|---|---|
| `--pr INT` | Open a specific pull request |
| `--issue INT` | Open a specific issue |
| `--pipeline TEXT` | Open a specific pipeline UUID |
| `--branch TEXT` | Open a specific branch view |

---

## completion

### `bb completion bash`

Print bash completion script.

### `bb completion zsh`

Print zsh completion script.

### `bb completion fish`

Print fish completion script.

### `bb completion powershell`

Print PowerShell completion script.

Source the output in your shell profile to enable tab completion.
