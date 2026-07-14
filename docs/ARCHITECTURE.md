# Architecture

## Module map

```
src/bb/
├── __init__.py          — package version (__version__)
├── cli.py               — root typer app; _GROUPS dict-dispatch; help/completion
│                          commands; single main() catch for BBError
└── core/
│   ├── config.py        — Settings dataclass; load_settings(); set_user_value()
│   ├── auth.py          — Credential/Credentials; resolve/save/delete;
│   │                      OS keyring + hosts.toml fallback;
│   │                      refresh_credential()/maybe_refresh() (OAuth rotation);
│   │                      git HTTPS Authorization helpers (extraHeader)
│   ├── oauth.py         — Bitbucket Cloud OAuth 2.0 authorization-code flow;
│   │                      resolve_oauth_client(); build_authorize_url();
│   │                      exchange_code(); refresh_access_token();
│   │                      run_loopback_login() (localhost HTTP callback server);
│   │                      no Typer imports — UI-agnostic, MockTransport-testable
│   ├── client.py        — ApiClient (httpx wrapper); make_client(); post_files();
│   │                      raw_request(); BBClient alias;
│   │                      _RefreshingBearerAuth (reactive 401→refresh→retry)
│   ├── context.py       — RepoContext; current_repo(); current_branch();
│   │                      git-remote → workspace/slug detection
│   ├── deployment.py    — Cloud/Data Center base URL and API URL resolution
│   ├── validation.py    — Pydantic gates for user-facing input
│   ├── output.py        — emit_table(); emit_json(); masked()
│   └── errors.py        — BBError hierarchy (AuthError, ApiError, ContextError,
│                          ConfigError)
└── commands/
    ├── auth.py           — login (token paste or browser OAuth) / logout /
    │                       status / token / refresh / setup-git
    ├── pr.py             — list / view (--comments) / create / checkout /
    │                       merge / close / reopen / edit / review / comment /
    │                       diff / checks / status
    ├── repo.py           — list / view / clone / create / fork / delete /
    │                       sync / edit / set-default
    ├── issue.py          — list / view / create / edit / close / reopen /
    │                       comment / delete / status
    ├── pipeline.py       — list / run / view / steps / logs / stop /
    │                       variable (list / create / delete)
    ├── branch.py         — list / create / delete
    ├── workspace.py      — list / view / members
    ├── project.py        — list / view / create
    ├── snippet.py        — list / view / create / edit / delete
    ├── search.py         — repos / code
    ├── status.py         — top-level dashboard (current user + PRs to review)
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
2. **Environment variables** — `BB_TOKEN`, `BB_BASE_URL`, `BB_REPO`, `BB_WORKSPACE`, `BB_EDITOR`,
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
5. OS keyring (`keyring` lib: macOS Keychain / XDG Secret Service / Windows Credential Locker)
6. `hosts.toml` in `platformdirs.user_config_dir("bb")` (mode 0600 fallback when keyring unavailable)

This precedence order is unchanged by OAuth support. Only sources 5 and 6 are
eligible for automatic refresh (`Credential.source in {"keyring", "hosts"}`);
see [OAuth module and refresh integration](#oauth-module-and-refresh-integration).

## OAuth module and refresh integration

`core/oauth.py` implements Bitbucket Cloud's OAuth 2.0 authorization-code
flow in isolation from Typer/CLI concerns — no `typer` import anywhere in the
module — so it stays testable with `httpx.MockTransport` and reusable outside
`bb auth login`:

- `OAuthClient(client_id, client_secret)` / `TokenResponse(access_token, refresh_token, expires_in)` — frozen dataclasses.
- `resolve_oauth_client()` — resolves consumer credentials env > config >
  embedded default; raises `AuthError` if no `client_id` is available.
- `build_authorize_url()` — builds the `bitbucket.org/site/oauth2/authorize` URL.
- `exchange_code()` / `refresh_access_token()` — `POST site/oauth2/access_token`
  with HTTP Basic `client_id:secret`; non-2xx responses raise `AuthError` with
  the status code only (body never surfaced).
- `run_loopback_login()` — binds an ephemeral `("localhost", 0)` HTTP server
  in a daemon thread, opens the browser (always also printing the URL as a
  fallback via an injectable `print_url` callback), waits on a
  `threading.Event` for the callback (success/deny/state-mismatch/timeout),
  then calls `exchange_code()`.

Full flow narrative, security properties, and consumer-registration steps:
see [docs/AUTH.md](AUTH.md).

**Refresh has two integration points**, both funneling through
`core/auth.py`'s `refresh_credential()` (does the actual token-endpoint call
+ persists the rotated `refresh_token`) and `maybe_refresh()` (the gate that
decides whether a refresh is due):

1. **Proactive** — `maybe_refresh()` wraps `resolve_credential()` in
   `client.py`'s `make_client()`, `raw_request()`, and `post_files()`, and in
   `commands/auth.py`'s `status`/`token` commands. Refreshes only
   keyring/hosts-sourced `auth_type=="oauth"` credentials within `skew=120s`
   of `expires_at`.
2. **Reactive** — `client.py`'s `_RefreshingBearerAuth` (an `httpx.Auth`,
   selected in `_build_auth()` only when `cred.auth_type == "oauth"`) catches
   a `401`, calls `refresh_credential()` once, retries the request once with
   the new token. Retry state is a local variable inside `auth_flow()`, not
   instance state, so one `httpx.Auth` instance reused across many requests
   on the same client can't leak retry bookkeeping between unrelated calls.

Because Bitbucket rotates the refresh token on every use, both paths funnel
through the same `refresh_credential()` → `save_credential()` write so the
newest refresh token is always the one persisted, regardless of which path
triggered the refresh.

## Layering invariants

1. `commands/*` may import any `core/*` module; never from other `commands/*`.
2. `core/*` modules import only stdlib and declared third-party deps; never from `commands/`.
3. `ApiClient` is the only HTTP path in the entire codebase. No command may call `httpx` directly.
4. `make_client()` in `client.py` is the only site where credentials are resolved and injected into HTTP API requests. HTTPS git clone/fetch/checkout additionally resolve credentials via `auth.git_command(..., https_auth=True)` and pass them to git as a one-shot `http.extraHeader` (not persisted in git config).
5. No secret values (raw token strings) may appear in output, log messages, or error text. Use `masked()` from `output.py` for any display that references a credential. (`bb auth token` and the git `extraHeader` argv are intentional exceptions for scripting / private HTTPS clone.)
6. `core/oauth.py` never imports `typer` and is never imported by `cli.py` directly — only `commands/auth.py` and `core/auth.py` import it (lazily, to avoid an `auth.py`↔`oauth.py` import cycle). OAuth token-endpoint response bodies, `code`, `refresh_token`, `client_secret`, and `state` are never surfaced in output, logs, or the loopback callback HTML — see `docs/AUTH.md`.

## Data flow

```
CLI arg parse (typer)
    → context resolve (context.py: BB_REPO env / --repo flag / git remote → workspace/slug or project/slug)
    → config merge (config.py: user cfg + project bb.toml + env vars)
    → deployment resolve (deployment.py: Cloud vs Data Center)
    → credential resolve (auth.py: env > .env > keyring > hosts.toml)
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
- **Global secret storage**: `bb auth login` (browser OAuth on Cloud+TTY, or
  a pasted token everywhere else) stores the credential once in the OS
  keyring (preferred). `hosts.toml` (mode 0600) is the fallback when no
  keyring backend is available (headless CI) — see `docs/AUTH.md`'s
  0600-fallback risk note for OAuth refresh tokens specifically. Env / `.env`
  still override for non-interactive agents, and are never auto-refreshed.
- **Browser OAuth is Cloud-only, TTY-gated**: `bb auth login` only attempts
  the loopback OAuth flow when the target deployment is Bitbucket Cloud *and*
  stdin is a TTY *and* no token flags were passed. Data Center always uses a
  Personal/HTTP Access Token; non-TTY invocations fail fast with a clear
  message rather than hanging on a browser that can't be opened. See
  `docs/AUTH.md` for the full routing table.
- **Cloud + Data Center**: Cloud uses `https://api.bitbucket.org/2.0`; Data
  Center/Server uses `<base_url>/rest/api/1.0`. Cloud-shaped repo paths are
  translated into Data Center project/repo REST paths by `core/client.py`.
  Workspace list/view map to DC projects; project `key` is normalized to
  `slug` so command tables and Cloud-shaped callers share one identifier.
- **Pydantic at the boundary**: `core/validation.py` validates high-risk
  user-facing inputs such as `base_url`, auth type, HTTP method, repo parts,
  and limits before lower-level modules use them.
- **`pr reopen` unsupported**: Bitbucket Cloud API has no reopen endpoint; the command surfaces a clear documented error rather than silently failing.
- **`help` and `completion` live in `cli.py`**: they are root `@app.command()`
  functions, not separate command modules, because they require no API calls.
  `help` walks the registered command tree so `bb help`, `bb help repo`, and
  `bb help repo list` use the same generated Typer help text as `--help`.
