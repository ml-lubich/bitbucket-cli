# Architecture

## Module map

```
src/bb/
├── __init__.py          — package version (__version__)
├── main.py              — entry point: calls cli.main()
├── cli.py               — root typer app; _GROUPS dict-dispatch; single main() catch
├── core/
│   ├── config.py        — Settings dataclass; load_settings(); set_user_value()
│   ├── auth.py          — Credentials dataclass; load_credentials(); save/clear
│   ├── client.py        — ApiClient (httpx wrapper); BBApiError; make_client()
│   ├── ctx.py           — RepoContext; git-remote → workspace/slug detection
│   ├── output.py        — emit_table(); emit_json(); masked(); --json flag handling
│   └── errors.py        — BBError hierarchy (AuthError, ApiError, ContextError, ConfigError)
└── commands/
    ├── auth.py           — login / logout / status
    ├── pr.py             — list / view / create / checkout / merge / close / edit / review / comment / diff / checks
    ├── repo.py           — list / view / clone / create / fork / delete / sync / set-default
    ├── issue.py          — list / view / create / edit / close / reopen / comment / delete
    ├── pipeline.py       — list / run / view / steps / logs / stop
    ├── branch.py         — list / create / delete
    ├── workspace.py      — list / view / members
    ├── project.py        — list / view / create
    ├── snippet.py        — list / view / create / edit / delete
    ├── api.py            — raw authenticated GET/POST/PATCH/DELETE
    ├── config_cmd.py     — get / set
    ├── browse.py         — open URLs in system browser
    └── completion.py     — bash / zsh / fish / powershell
```

## Layers

```
CLI (typer app + commands/)
    ↓ imports
core/ (config, auth, client, ctx, output, errors)
    ↓ imports
stdlib + third-party (httpx, platformdirs, tomlkit, rich)
```

Commands import from `core/`. Core modules do not import from `commands/`.
No circular imports are permitted.

## Layering invariants

1. `commands/*` may import any `core/*` module and nothing from other `commands/*`.
2. `core/*` modules import only stdlib and declared dependencies; never from `commands/`.
3. `ApiClient` is the only HTTP path in the entire codebase. No command may call `httpx` directly.
4. `make_client()` (in `client.py`) is the only site where credentials are resolved and injected into a request. No command reads `Credentials` directly.
5. No secret values (raw token strings) may appear in output, log messages, or error text. Use `masked()` from `output.py` for any display that references a credential.

## Data flow

```
CLI arg parse (typer)
    → context resolve (ctx.py: git remote → workspace/slug)
    → config merge (config.py: user cfg + project cfg + env)
    → credential resolve (auth.py: env > .env > hosts.toml)
    → ApiClient.request() (client.py: httpx, Bearer header, pagination)
    → emit (output.py: rich table or JSON to stdout)
```

## Error model

- `BBError(message, exit_code=1)` — base; caught in `cli.main()`.
- `AuthError(BBError)` — missing or invalid credentials; exit 1.
- `ApiError(BBError)` — HTTP error from Bitbucket; carries status code in message; exit 1.
- `ContextError(BBError)` — no Bitbucket git remote detected; exit 1.
- `ConfigError(BBError)` — invalid config key or value; exit 1.
- `RepoContextError` (legacy alias in `ctx.py`) — also caught in `cli.main()`.
- All exceptions surface via `cli.main()`'s single `except` chain; no command swallows errors silently.
- Exit code 0 = success. Exit code 1 = any `BBError` subclass or auth failure.

## Key design decisions

- **Dict-dispatch group registration** (`_GROUPS` in `cli.py`) keeps `cli.py` decoupled from command implementations; adding a group is one dict entry + one import.
- **Injected transport seam** (`ApiClient` accepts an optional `httpx.MockTransport`): tests pass a mock transport rather than patching module globals.
- **No OAuth browser flow in v0.1**: token paste only; scope left for v0.2.
- **Bitbucket Cloud API 2.0 only**: no Server/DC support.
- **`pr reopen` unsupported**: Bitbucket Cloud API has no reopen endpoint; the command surfaces a clear documented error rather than crashing.
