# Architecture

## Module map

```
src/bb/
├── __init__.py          — package version (__version__)
├── cli.py               — root typer app; _GROUPS dict-dispatch; help/completion
│                          commands; single main() catch for BBError
└── core/
│   ├── config.py        — Settings dataclass; load_settings(); set_user_value()
│   ├── auth.py          — Credential/Credentials dataclasses; resolve_credential();
│   │                      save_credential(); delete_credential()
│   ├── client.py        — ApiClient (httpx wrapper); make_client(); post_files();
│   │                      raw_request(); BBClient alias
│   ├── context.py       — RepoContext; current_repo(); current_branch();
│   │                      git-remote → workspace/slug detection
│   ├── output.py        — emit_table(); emit_json(); masked()
│   └── errors.py        — BBError hierarchy (AuthError, ApiError, ContextError,
│                          ConfigError)
└── commands/
    ├── auth.py           — login / logout / status
    ├── pr.py             — list / view / create / checkout / merge / close /
    │                       reopen / edit / review / comment / diff / checks
    ├── repo.py           — list / view / clone / create / fork / delete /
    │                       sync / set-default
    ├── issue.py          — list / view / create / edit / close / reopen /
    │                       comment / delete
    ├── pipeline.py       — list / run / view / steps / logs / stop
    ├── branch.py         — list / create / delete
    ├── workspace.py      — list / view / members
    ├── project.py        — list / view / create
    ├── snippet.py        — list / view / create / edit / delete
    ├── api.py            — raw authenticated request (GET/POST/PUT/DELETE)
    ├── config_cmd.py     — get / set
    └── browse.py         — open URLs in system browser
```

## Layers

```
CLI (cli.py + commands/)
    ↓ imports
core/ (config, auth, client, context, output, errors)
    ↓ imports
stdlib + third-party (httpx, platformdirs, tomlkit, rich, typer)
```

Commands import from `core/`. Core modules do not import from `commands/`.
No circular imports are permitted.

## Config layering precedence (contract — changing order is a breaking change)

Priority order (1 = highest):

1. **CLI arguments** — `--repo`, `--workspace`, etc. passed on the command line
2. **Environment variables** — `BB_TOKEN`, `BB_REPO`, `BB_WORKSPACE`, `BB_EDITOR`,
   `BB_GIT_PROTOCOL`
3. **Project config** — `bb.toml` at the current working directory (repo root)
4. **User config** — `config.toml` in `platformdirs.user_config_dir("bb")`
   (e.g. `~/.config/bb/config.toml` on Linux, `~/Library/Application Support/bb/config.toml` on macOS)
5. **Hardcoded defaults** — `git_protocol=https`, others empty string

Token resolution (auth.py, separate from config.py):

1. `BB_TOKEN` env var
2. `BITBUCKET_TOKEN` env var
3. `BITBUCKET_AUTH_TOKEN` env var
4. Repo-local `.env` file (same three keys parsed as `KEY=VALUE` lines)
5. `hosts.toml` in `platformdirs.user_config_dir("bb")` (written by `bb auth login`, mode 0600)

## Layering invariants

1. `commands/*` may import any `core/*` module; never from other `commands/*`.
2. `core/*` modules import only stdlib and declared third-party deps; never from `commands/`.
3. `ApiClient` is the only HTTP path in the entire codebase. No command may call `httpx` directly.
4. `make_client()` in `client.py` is the only site where credentials are resolved and injected into a request.
5. No secret values (raw token strings) may appear in output, log messages, or error text. Use `masked()` from `output.py` for any display that references a credential.

## Data flow

```
CLI arg parse (typer)
    → context resolve (context.py: BB_REPO env / --repo flag / git remote → workspace/slug)
    → config merge (config.py: user cfg + project bb.toml + env vars)
    → credential resolve (auth.py: env > .env > hosts.toml)
    → ApiClient.request() (client.py: httpx, Bearer or BasicAuth header, pagination)
    → emit (output.py: rich table or JSON to stdout)
```

## Error model

- `BBError(message, exit_code=1)` — base; caught in `cli.main()`.
- `AuthError(BBError)` — missing or invalid credentials; exit 1.
- `ApiError(BBError)` — HTTP error from Bitbucket; carries HTTP status code in message text; exit 1.
- `ContextError(BBError)` — no Bitbucket git remote detected and no override supplied; exit 1.
- `ConfigError(BBError)` — unknown config key or bad value; exit 1.
- All exceptions surface via `cli.main()`'s single `except BBError` block. No command swallows errors silently.
- Exit code 0 = success. Exit code 1 = any `BBError` subclass or unhandled error.

## Key design decisions

- **Dict-dispatch group registration** (`_GROUPS` in `cli.py`) keeps `cli.py` decoupled from command implementations; adding a group is one dict entry and one import.
- **Injected transport seam** (`ApiClient` and `raw_request()` accept an optional `httpx.BaseTransport`): tests pass a `MockTransport` rather than patching module globals.
- **No OAuth browser flow in v0.1**: token paste only; interactive auth left for a later version.
- **Bitbucket Cloud API 2.0 only**: no Server or Data Center support.
- **`pr reopen` unsupported**: Bitbucket Cloud API has no reopen endpoint; the command surfaces a clear documented error rather than silently failing.
- **`help` and `completion` live in `cli.py`**: they are root `@app.command()`
  functions, not separate command modules, because they require no API calls.
  `help` walks the registered command tree so `bb help`, `bb help repo`, and
  `bb help repo list` use the same generated Typer help text as `--help`.
