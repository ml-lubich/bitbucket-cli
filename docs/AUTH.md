# Authentication

`bb` supports two login paths on Bitbucket Cloud — browser OAuth (interactive)
and manual token paste (headless/CI/Data Center) — plus environment-variable
and `.env` overrides for scripting. This document covers the OAuth flow in
detail, the token-refresh model, credential precedence, and how to point `bb`
at your own OAuth consumer.

---

## `bb auth login` routing

`bb auth login` decides how to authenticate based on the target deployment
(Cloud vs Data Center), whether token flags were passed, and whether stdin is
a TTY:

| Condition | Behavior |
|---|---|
| `--token` or `--with-token` given | Manual path: store the given token directly (any deployment). |
| Data Center, no token flags, TTY | Prints `Data Center requires a token. Run: bb auth login --with-token`, then falls through to an interactive token prompt. Never opens a browser. |
| Data Center, no token flags, non-TTY | Prints the same message to stderr and exits 1. |
| Cloud, no token flags, non-TTY | Prints `not a terminal — pass --with-token, --token, or set BB_TOKEN` and exits 1. No hang, no browser attempt. |
| Cloud, no token flags, TTY | **Browser OAuth 2.0 authorization-code flow** (below). |

Data Center never performs browser OAuth — Bitbucket Data Center/Server has no
Atlassian-SSO-backed OAuth consumer flow reachable from a generic CLI; use a
Personal/HTTP Access Token via `bb auth login --with-token`.

---

## Browser OAuth flow (Bitbucket Cloud)

1. **Resolve the OAuth consumer.** `bb` needs a registered Bitbucket OAuth
   consumer's `client_id`/`client_secret`. Resolution order:
   1. Env vars `BB_OAUTH_CLIENT_ID` / `BB_OAUTH_CLIENT_SECRET`
   2. Config keys `oauth_client_id` / `oauth_client_secret` (`bb config set …`)
   3. Embedded defaults baked into the release (populated by the maintainer
      after registering a public consumer — see
      [Registering a consumer](#registering-a-consumer-maintainers--orgs) below)

   If no `client_id` can be resolved from any of the three, login fails
   immediately with a clear error pointing at `--with-token` as a fallback —
   it never hangs waiting on a browser that can't be authorized.

2. **Start a loopback callback server.** `bb` generates a random
   `state` value (`secrets.token_urlsafe(32)`) and binds an ephemeral HTTP
   server on `("localhost", 0)` (OS-assigned free port, up to 5 bind
   retries). The redirect URI is `http://localhost:{port}/callback` —
   deliberately `localhost`, not `127.0.0.1`, per RFC 8252 loopback
   semantics: a consumer registered with the bare callback URL
   `http://localhost` accepts any dynamically chosen port at request time.

3. **Open the browser.** `bb` calls `webbrowser.open(authorize_url)` and
   **always** also prints the authorize URL to the terminal as a fallback —
   if the browser can't be launched (headless-over-SSH-with-X-forwarding
   quirks, sandboxed environments, etc.) you can copy/paste the URL manually.
   The wait continues either way.

4. **Wait for the callback**, up to a 120-second hard timeout. Three outcomes:
   - **Success** — the browser redirects to `/callback?code=…&state=…`. `bb`
     verifies `state` with `secrets.compare_digest` (constant-time, prevents
     CSRF), serves a static "Login successful — you can close this tab" HTML
     page (no code, token, or state ever appears in the page), and signals
     the main thread.
   - **Denied** (`?error=…` on the callback) — immediate failure (does not
     wait for the timeout), serves an error page, exits 1.
   - **State mismatch** — immediate failure, exits 1, message mentions
     possible CSRF.
   - **Timeout** (120s with no callback) — clean server shutdown, fallback
     message, exits 1.

5. **Exchange the code for tokens.** `POST https://bitbucket.org/site/oauth2/access_token`
   with HTTP Basic `client_id:client_secret` and
   `grant_type=authorization_code&code=…&redirect_uri=…`. A non-2xx response
   fails with just the HTTP status code — the response body is never echoed
   (it can contain request-parameter reflections unsuitable for a terminal).

6. **Store the credential.** On success `bb` builds
   `Credential(auth_type="oauth", token=access_token, refresh_token=…, expires_at=now + expires_in)`,
   verifies it with `GET /user` (unless `--no-verify`), saves it to the OS
   keyring (or the 0600 fallback file — see
   [Storage and security](#storage-and-security)), and prints
   `logged in as <display_name>`.

Nothing sensitive (`code`, `access_token`, `refresh_token`, `client_secret`,
`state`) is ever written to stdout, stderr, or the callback HTML.

### Scopes

The authorize request requests this fixed scope set:

```
account repository:write pullrequest:write issue:write pipeline:write pipeline:variable webhook project snippet:write
```

This is the scope superset needed for every `bb` write command (PRs, issues,
pipeline variables, webhooks, projects, snippets). There is no `--scopes`
flag — Bitbucket OAuth consumers grant scopes at consumer-registration time
per Atlassian's model, not per-request beyond what the consumer allows.

---

## Token refresh: rotation model

Bitbucket Cloud OAuth access tokens are short-lived (`expires_in`, typically
~2 hours) and **refresh tokens rotate on every use** — each refresh call
returns a brand-new `refresh_token` and immediately invalidates the old one.
`bb` treats the "newest known refresh token" as the single source of truth
and persists it after every refresh.

Two integration points, both funneling through `core/auth.py`:

- **Proactive refresh** — `maybe_refresh(cred, skew=120.0)` is called before
  every API request (`make_client()`, `raw_request()`, `post_files()`) and
  by `bb auth status` / `bb auth token`. It refreshes only when:
  - `cred.auth_type == "oauth"`
  - a `refresh_token` is present
  - the credential came from a **persistent store** (`source in {"keyring", "hosts"}`
    — env-var and `.env`-sourced tokens are never auto-refreshed, since `bb`
    has no way to persist a rotated token back into your shell environment)
  - `expires_at` is set and within `skew` seconds of now (or already past)

  A successful proactive refresh calls `refresh_credential()`, which persists
  the rotated pair back to the keyring/hosts store before the request
  proceeds.

- **Reactive refresh** — `_RefreshingBearerAuth` (an `httpx.Auth` used only
  for `auth_type == "oauth"` credentials, wired in `client.py`'s
  `_build_auth`) catches a `401` response, refreshes once via
  `refresh_credential()`, and retries the request once with the new token.
  This is the safety net for clock skew or a token that expired between
  proactive-refresh time and the actual request. Basic-auth and plain
  static-bearer credentials are untouched by this path.

If a refresh fails (the refresh token was revoked or expired — Bitbucket
expires an *unused* refresh token after ~3 months), `bb` raises
`AuthError("token refresh failed — run \`bb auth login\` (...)")`. This exits
1 with a clean message; it never loops or retries indefinitely.

`bb auth refresh` forces a refresh on demand (useful for scripting or to
confirm a stored OAuth login is still valid); it returns a friendly error if
the current credential is not an OAuth login (e.g. it's a manually pasted
token or Basic-auth credential).

`git_command()` / `git_https_config_args()` (used by `bb repo clone`,
`repo sync`, `pr checkout`, and `bb auth setup-git`) also route through
`maybe_refresh()` so a near-expiry OAuth token is refreshed before being
handed to `git` as an HTTPS `Authorization` header.

---

## Credential precedence contract

Resolution order is unchanged by OAuth support (`core/auth.py:resolve_credential`);
first match wins:

| Priority | Source | Auto-refreshed? |
|---|---|---|
| 1 | `BB_TOKEN` env var | No |
| 2 | `BITBUCKET_TOKEN` env var | No |
| 3 | `BITBUCKET_AUTH_TOKEN` env var | No |
| 4 | Repo-local `.env` file | No |
| 5 | OS keyring | Yes, if `auth_type=="oauth"` |
| 6 | `hosts.toml` fallback (mode 0600) | Yes, if `auth_type=="oauth"` |

Only credentials sourced from the keyring or the `hosts.toml` fallback are
eligible for automatic refresh — this is a deliberate design choice: env/`.env`
tokens are assumed to be externally managed (CI secret injection, a script
that re-exports a fresh token each run) and `bb` has no mechanism to write a
rotated token back into the process environment or a `.env` file, so it never
tries.

Legacy stored credentials (from before OAuth support existed) have no
`refresh_token`/`expires_at` fields; they load with those fields defaulted to
empty/zero and behave exactly as a static bearer/basic token always did — no
behavior change, no forced re-login.

---

## Configuration keys

Two new config keys (both readable via `bb config get` / writable via
`bb config set`, and overridable by matching env vars — env always wins):

| Config key | Env var | Purpose |
|---|---|---|
| `oauth_client_id` | `BB_OAUTH_CLIENT_ID` | Override the OAuth consumer `client_id` used for `bb auth login`. |
| `oauth_client_secret` | `BB_OAUTH_CLIENT_SECRET` | Override the OAuth consumer `client_secret`. |

```bash
bb config set oauth_client_id "your-consumer-key"
bb config set oauth_client_secret "your-consumer-secret"
# or, for CI / one-shot overrides:
export BB_OAUTH_CLIENT_ID="your-consumer-key"
export BB_OAUTH_CLIENT_SECRET="your-consumer-secret"
```

Use this when you want browser-OAuth logins to run under your own
organization's Bitbucket OAuth consumer instead of the CLI's embedded default
(e.g. to get an audit trail scoped to your own workspace, or because your
org's security policy requires it).

---

## Registering a consumer (maintainers / orgs)

To enable (or replace) the embedded OAuth consumer, register one in Bitbucket
Cloud:

1. Go to the target workspace → **Settings → OAuth consumers → Add consumer**.
2. **Callback URL: `http://localhost`** — register the bare URL with no port.
   Bitbucket's OAuth implementation follows RFC 8252 loopback-redirect
   behavior, so a request-time redirect URI of
   `http://localhost:{ephemeral-port}/callback` is accepted even though the
   consumer's registered callback has no port. Do **not** register a specific
   port — `bb` binds a fresh ephemeral port on every login.
3. Grant the permissions matching `DEFAULT_SCOPES` in `src/bb/core/oauth.py`
   (Account, Repositories: Write, Pull requests: Write, Issues: Write,
   Pipelines: Write, Webhooks, Projects, Snippets: Write) — or a subset if
   your org doesn't need every `bb` write command.
4. Save, then copy the generated **Key** (client_id) and **Secret**
   (client_secret).
5. Either:
   - Set them as `BB_OAUTH_CLIENT_ID`/`BB_OAUTH_CLIENT_SECRET` for your users
     to export, or `bb config set oauth_client_id/oauth_client_secret` for a
     durable per-machine default; or
   - If you maintain a `bb` fork/release, populate `_EMBEDDED_CLIENT_ID` /
     `_EMBEDDED_CLIENT_SECRET` in `src/bb/core/oauth.py` before building so
     `bb auth login` works out of the box with no configuration step.

The client secret shipped this way is a **low-value public identifier**, not
a high-value secret: Bitbucket's OAuth flow still requires every individual
user to approve the authorization in their own browser session, so an
embedded secret does not itself grant access to anyone's account. Treat it
the same way `gh`, `git`, and most public CLIs treat their embedded
`client_id` — scope the consumer's permissions conservatively and rotate it
if it is ever implicated in abuse.

---

## Data Center / headless fallback

Bitbucket Data Center/Server has no equivalent of Bitbucket Cloud's
Atlassian-SSO OAuth consumer flow reachable generically from a CLI (its OAuth
support, where enabled at all, is wired per-instance through Application
Links and is out of scope for `bb`). `bb auth login` against a Data Center
`base_url` always routes to the manual token path:

```bash
bb config set base_url https://bitbucket.yourcompany.com
bb auth login --with-token   # paste a Personal/HTTP Access Token
```

The same manual path is also the correct choice for:

- **CI/CD and other non-interactive environments** — no TTY means `bb` never
  attempts a browser flow (it would hang or fail confusingly if it tried).
  Use `BB_TOKEN` or `bb auth login --with-token < token-file`.
- **Remote/headless shells with no local browser** — pass `--with-token` /
  `--token` instead of relying on the loopback flow (which does still print
  the URL for manual copy into a local browser, but is more friction than
  a direct token paste for a fully headless box).

---

## Storage and security

- **Preferred storage**: OS keyring (macOS Keychain, Linux Secret Service /
  GNOME Keyring / KWallet, Windows Credential Locker) via the `keyring`
  library. The stored payload is a JSON blob:
  `{"token", "auth_type", "username", "refresh_token", "expires_at"}`.
  A non-secret mirror entry (`auth_type`, `storage="keyring"`, `username`)
  is written to `hosts.toml` purely so `bb auth status`/`doctor` can report
  the auth type without touching the keyring; it never contains a token or
  refresh token.

- **0600 fallback file risk**: when no keyring backend is available (common
  in minimal CI containers, some headless Linux setups without a Secret
  Service provider, or `keyring` not installed), `bb` falls back to writing
  the full credential — **including `refresh_token`** — into
  `hosts.toml` at `platformdirs.user_config_dir("bb")`
  (e.g. `~/.config/bb/hosts.toml`) with file mode `0600`. This is
  plaintext-on-disk, readable by the file owner only. Understand the
  implications before relying on this fallback for OAuth logins in shared or
  multi-tenant environments:
  - `0600` only protects against *other local users*, not against anyone with
    root, backup access, or a compromised account.
  - The refresh token is long-lived (~3 months from last use) and, unlike a
    revoked access token, **rotates silently on every use** — a leaked
    refresh token from this file keeps working (and keeps rotating itself)
    until either the account owner revokes it via Bitbucket's OAuth-consumer
    "Access tokens" management UI or it goes 3 months unused.
  - If you're on a shared/CI machine without a keyring, prefer the manual
    `--with-token` path with a short-lived Atlassian API token over browser
    OAuth, precisely to avoid landing a rotating refresh token in a plaintext
    file.

- **`bb auth logout`** removes the credential from both the keyring and the
  `hosts.toml` entry (secret and metadata) for the current host.

- **Nothing is ever printed**: `code`, `access_token`, `refresh_token`,
  `client_secret`, and `state` are never written to stdout, stderr, or the
  loopback callback HTML at any point in the flow. `bb auth token` (which
  intentionally prints the *current* access token for scripting) and the
  git `http.extraHeader` argv passed to `git` subprocesses (necessary for
  authenticated HTTPS clone/fetch) are the only deliberate exceptions —
  documented in `docs/ARCHITECTURE.md`'s layering invariants.

- **Cross-process refresh races**: refresh is best-effort and not
  cross-process-locked. If two `bb` invocations race to refresh the same
  near-expiry OAuth credential concurrently, both will call the token
  endpoint; because refresh tokens rotate, the loser's rotated
  `refresh_token` write can be immediately stale. In practice this only
  matters for tight concurrent scripting against the same host and is a
  documented limitation, not a crash — the next command run will proactively
  refresh again (or hit the reactive-401 path) and self-heal.

---

## See also

- [Architecture: OAuth module and refresh integration points](ARCHITECTURE.md#oauth-module-and-refresh-integration)
- [README: Authentication](../README.md#authentication)
- `src/bb/core/oauth.py` — the OAuth client (no Typer imports; UI-agnostic,
  testable with `httpx.MockTransport`)
- `src/bb/core/auth.py` — credential storage, `refresh_credential()`,
  `maybe_refresh()`
