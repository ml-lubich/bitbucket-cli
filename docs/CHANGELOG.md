# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-14

### Added

- **Browser OAuth login**: `bb auth login` with no token flags, on Bitbucket
  Cloud, in an interactive terminal, now performs a browser OAuth 2.0
  authorization-code flow (Atlassian SSO) — opens the browser, runs a
  localhost loopback callback server, exchanges the code for an access +
  rotating refresh token, and stores both in the OS keyring. See
  [docs/AUTH.md](AUTH.md) for the full flow and security model. Data Center,
  non-interactive shells, and `--token`/`--with-token` invocations are
  unaffected and never attempt a browser flow.
- Transparent OAuth token refresh — proactive (before requests near expiry)
  and reactive (on a `401`, refresh once and retry once) — with rotation
  persistence, since Bitbucket issues a new refresh token on every use.
  Confined to `core/auth.py` and `core/client.py`; env/`.env`-sourced tokens
  are never auto-refreshed.
- `bb auth refresh` — force a token refresh for an OAuth login.
- `bb auth setup-git` — print the `git -c` flags that authenticate HTTPS
  clone/fetch/push with the currently stored credential.
- New config keys `oauth_client_id` / `oauth_client_secret` and env vars
  `BB_OAUTH_CLIENT_ID` / `BB_OAUTH_CLIENT_SECRET` to point browser login at a
  self-registered Bitbucket OAuth consumer instead of the embedded default.
- `bb repo edit` — update repository description, visibility (`--private`/`--public`),
  project, or name via `PUT /repositories/{workspace}/{repo}`.
- `bb pr status` — pull requests you created and pull requests awaiting your
  review, grouped and tabled.
- `bb pr view --comments` — print PR comments after the detail view.
- `bb issue status` — issues reported by you and issues assigned to you,
  grouped and tabled.
- `bb status` — top-level dashboard: authenticated user plus pull requests
  awaiting your review in the current repo.
- `bb search repos` / `bb search code` — search repositories by name or
  search code within a workspace.
- `bb pipeline variable list` / `create` / `delete` — manage Pipelines
  repository variables, including `--secured` variables (value never echoed
  back).
- `bb api`: renamed `-f/--field` to `-f/--raw-field` (string body/query
  fields) and added `-F/--field` with gh-style type coercion (`true`/`false`/
  `null`/int; everything else stays a string). Added `--paginate` (follow
  `next` pagination links, concatenating `values` arrays; `--limit` caps the
  total items returned) and `--jq` (filter the JSON response through a
  system `jq` binary — must be installed and on `PATH`).
- `bb browse` gained a positional `TARGET` argument (a PR number opens that
  pull request; a file path opens the source view, honoring `-b/--branch`),
  `-b/--branch` (open the source tree at a branch), `-c/--commit` (open a
  commit), and `-n/--no-browser` as an alias of `--no-open`.

### Changed

- `auth_type` now accepts `"oauth"` in addition to `"bearer"`/`"basic"`
  (`core/validation.py`).

### gh-parity decisions (verified Bitbucket Cloud endpoints only)

| Command | Endpoint | Verdict |
|---|---|---|
| `auth refresh` | `POST site/oauth2/access_token` | INCLUDE |
| `auth setup-git` | local git config only | INCLUDE |
| `repo edit` | `PUT /repositories/{ws}/{repo}` | INCLUDE |
| `repo rename` / `repo archive` | none on Cloud | OMIT |
| `pr status` | `GET …/pullrequests?q=` + `/user` uuid | INCLUDE |
| `pr ready` | no draft-toggle endpoint | OMIT |
| `pr view --comments` | `GET …/pullrequests/{id}/comments` | INCLUDE |
| `issue status` | `GET …/issues?q=reporter/assignee` | INCLUDE |
| `status` (top-level dashboard) | `/user` + reviewer PR query | INCLUDE |
| `search repos` | `GET /repositories/{ws}?q=name~"…"` | INCLUDE |
| `search code` | `GET /workspaces/{ws}/search/code?search_query=` | INCLUDE |
| `pipeline variable list/create/delete` | `…/pipelines_config/variables/` | INCLUDE |
| `label` / `release` | no Bitbucket API | OMIT |

## [0.2.0] - 2026-07-09

### Changed

- PyPI distribution renamed to `bitbucket-bb` because `bitbucket-cli` is an
  unrelated legacy package on PyPI. The `bb` console script is unchanged.

### Added

- OS keyring storage for tokens (macOS Keychain / Linux Secret Service /
  Windows Credential Locker) via `keyring`; `hosts.toml` mode 0600 remains
  the fallback when no keyring backend is available.
- `bb auth login --with-token` reads a token from stdin.
- `bb auth token` prints the active token for scripting.
- Pydantic `validate_limit` wired into list commands (`pr`, `repo`, `issue`,
  `branch`, `pipeline`).
- Bitbucket Data Center / Server support (`base_url`, path translation,
  `bb doctor`).

### Fixed

- `bb repo clone` / `repo sync` / `pr checkout` HTTPS git operations now inject
  the stored credential via `git -c http.extraHeader=Authorization: …`, so
  private repos no longer fail with "could not read Username".
- Data Center `bb workspace list` / `workspace view` now populate `slug` from
  the project `key` (DC has no workspace slug field). `/workspaces/{key}` maps
  to `/projects/{key}`.

### Removed

- Browser / `--web` OAuth login flow (token paste + keyring is the supported path).

## [0.1.2] - 2026-06-14

### Changed

- Bumped package version to 0.1.2.
- Replaced the package author email with the public GitHub noreply address for
  open-source publishing.
- Added `bb help [COMMAND...]` and `-h` as a short help alias across root,
  command groups, and subcommands.
- Added a `raw_request()` transport seam so raw API, pipeline log, and snippet
  raw-content paths can be tested through `httpx.MockTransport` without live
  Bitbucket access or `httpx.Client` monkeypatching.
- Documented the supported `UV_PROJECT_ENVIRONMENT=venv uv run ...` execution
  path used by `scripts/setup.sh`.

## [0.1.0] - 2026-06-11

### Added

- Token authentication: `bb auth login` (prompts securely or accepts `--token`),
  `bb auth logout`, `bb auth status`.
  - `--username TEXT` flag on `auth login` for basic auth.
  - `--no-verify` flag to skip GET /user verification after storing.
  - Token resolution order: `BB_TOKEN` env > `BITBUCKET_TOKEN` env >
    `BITBUCKET_AUTH_TOKEN` env > repo-local `.env` file > `hosts.toml`
    (mode 0600, platformdirs user config dir).
  - Credentials never echoed; `masked()` used for any display reference.
- Pull request commands: `pr list`, `pr view`, `pr create`, `pr checkout`,
  `pr merge`, `pr close`, `pr edit`, `pr review`, `pr comment`, `pr diff`,
  `pr checks`.
  - `pr list` supports `--state`, `--limit`, `--reviewer`, `--json`.
  - `pr create` supports `--base`, `--head`, `--draft`, `--close-source-branch`.
  - `pr merge` supports `--merge-strategy` (merge_commit / squash / fast_forward),
    `--delete-branch`, `--message`.
  - `pr review` supports `--approve`, `--request-changes`, `--unapprove`, `--body`.
  - `pr reopen` surfaces a documented error (Bitbucket Cloud API has no reopen endpoint).
- Repository commands: `repo list`, `repo view`, `repo clone`, `repo create`,
  `repo fork`, `repo delete`, `repo sync`, `repo set-default`.
  - Clone respects `git_protocol` config key (`https` or `ssh`).
  - `repo set-default` writes `default_repo` into `bb.toml` at git root.
- Issue tracker commands: `issue list`, `issue view`, `issue create`,
  `issue edit`, `issue close`, `issue reopen`, `issue comment`, `issue delete`.
  - Clear error when issue tracker is disabled for a repo (API 404).
- Pipeline commands: `pipeline list`, `pipeline run`, `pipeline view`,
  `pipeline steps`, `pipeline logs`, `pipeline stop`.
  - `pipeline logs --step TEXT` accepts step UUID; omit for all steps.
- Branch commands: `branch list`, `branch create`, `branch delete`.
  - `branch create --from TEXT` to specify source commit or branch.
- Workspace commands: `workspace list`, `workspace view`, `workspace members`.
- Project commands: `project list`, `project view`, `project create`.
- Snippet commands: `snippet list`, `snippet view`, `snippet create`,
  `snippet edit`, `snippet delete`.
  - `snippet view` and `snippet delete` take `WORKSPACE SNIP_ID` positional args.
  - `snippet view --raw --file TEXT` for raw file content.
- Raw API command: `bb api [ENDPOINT]` with `-X / --method`, `-f / --field`,
  `--paginate`, `--input TEXT`.
  - `bb api request` subcommand alias.
- `bb browse [--repo] [--branch] [--no-open]` — open current repo in browser.
- `bb completion <SHELL>` — print shell completion script for bash, zsh, fish,
  or powershell.
- Config layering: CLI args > env vars > project `bb.toml` > user `config.toml`
  (platformdirs) > defaults.
  - Valid keys: `git_protocol`, `editor`, `default_repo`, `default_workspace`.
  - `config get <KEY>` and `config set <KEY> <VALUE>` subcommands.
- Plain table output (rich) and `--json` flag on all list/view commands.
- Global `-R / --repo TEXT` flag to override git-remote context detection.
- `BBError` hierarchy: `AuthError`, `ApiError`, `ContextError`, `ConfigError`;
  single catch in `cli.main()`.
- `scripts/setup.sh`: idempotent uv-based setup for macOS and Linux.
- Five canonical docs under `docs/`: ARCHITECTURE, API, TESTING, RUNBOOK,
  CHANGELOG.
