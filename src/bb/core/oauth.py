"""
oauth.py — Bitbucket Cloud OAuth 2.0 authorization-code flow (browser login).

Inputs : OAuthClient (client_id/secret from env > config > embedded default),
         a loopback HTTP callback on localhost.
Outputs: TokenResponse (access_token, refresh_token, expires_in).
Failure: AuthError on denial, state mismatch, timeout, or a non-2xx token
         response. Token-endpoint response bodies are never surfaced in
         error messages, and no secret (code/token/state) is ever printed
         or embedded in the callback HTML.

No Typer imports here — this module is UI-agnostic so it stays testable
with MockTransport and reusable outside the `auth login` command.
"""
from __future__ import annotations

import http.server
import os
import secrets
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from bb.core.errors import AuthError

AUTHORIZE_URL = "https://bitbucket.org/site/oauth2/authorize"
TOKEN_URL = "https://bitbucket.org/site/oauth2/access_token"
DEFAULT_SCOPES = (
    "account repository:write pullrequest:write issue:write "
    "pipeline:write pipeline:variable webhook project snippet:write"
)
# Maintainer populates these after registering a Bitbucket OAuth consumer
# (Workspace settings → OAuth consumers). Until then, callers must supply
# BB_OAUTH_CLIENT_ID/BB_OAUTH_CLIENT_SECRET or config oauth_client_id/secret.
_EMBEDDED_CLIENT_ID = ""
_EMBEDDED_CLIENT_SECRET = ""

CALLBACK_TIMEOUT = 120.0
PORT_RETRIES = 5

_SUCCESS_HTML = """<!doctype html>
<html><head><title>bb — logged in</title></head>
<body style="font-family: sans-serif; text-align: center; margin-top: 10%;">
<h1>Login successful</h1>
<p>You can close this tab and return to your terminal.</p>
</body></html>
"""

_ERROR_HTML = """<!doctype html>
<html><head><title>bb — login failed</title></head>
<body style="font-family: sans-serif; text-align: center; margin-top: 10%;">
<h1>Login failed</h1>
<p>{message}</p>
<p>You can close this tab and return to your terminal.</p>
</body></html>
"""


@dataclass(frozen=True)
class OAuthClient:
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int


def resolve_oauth_client() -> OAuthClient:
    """Resolve OAuth consumer credentials: env > config > embedded default."""
    client_id = os.environ.get("BB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("BB_OAUTH_CLIENT_SECRET", "")
    if not client_id:
        client_id = _config_value("oauth_client_id")
        client_secret = client_secret or _config_value("oauth_client_secret")
    if not client_id:
        client_id = _EMBEDDED_CLIENT_ID
        client_secret = client_secret or _EMBEDDED_CLIENT_SECRET
    if not client_id:
        raise AuthError(
            "no OAuth client configured — set BB_OAUTH_CLIENT_ID/BB_OAUTH_CLIENT_SECRET "
            "or `bb config set oauth_client_id/oauth_client_secret`, or use `bb auth login --with-token`"
        )
    return OAuthClient(client_id=client_id, client_secret=client_secret)


def _config_value(key: str) -> str:
    from bb.core.config import get_value

    try:
        return get_value(key)
    except Exception:
        return ""


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: str = DEFAULT_SCOPES,
) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if scopes:
        params["scope"] = scopes
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(
    client: OAuthClient,
    code: str,
    redirect_uri: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> TokenResponse:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    return _token_request(client, data, transport=transport)


def refresh_access_token(
    client: OAuthClient,
    refresh_token: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> TokenResponse:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return _token_request(client, data, transport=transport)


def _token_request(
    client: OAuthClient,
    data: dict[str, str],
    *,
    transport: httpx.BaseTransport | None = None,
) -> TokenResponse:
    kwargs: dict[str, object] = {}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as http_client:  # type: ignore[arg-type]
            resp = http_client.post(
                TOKEN_URL,
                data=data,
                auth=(client.client_id, client.client_secret),
            )
    except httpx.HTTPError as exc:
        raise AuthError(f"OAuth token request failed: {exc.__class__.__name__}") from exc
    if resp.is_error:
        # Never surface the response body — it may echo request params or
        # leak internal error detail unsuitable for terminal output.
        raise AuthError(f"OAuth token request failed with status {resp.status_code}")
    try:
        payload = resp.json()
    except Exception as exc:
        raise AuthError("OAuth token response was not valid JSON") from exc
    access_token = str(payload.get("access_token", ""))
    if not access_token:
        raise AuthError("OAuth token response did not include an access token")
    refresh_token = str(payload.get("refresh_token", ""))
    try:
        expires_in = int(payload.get("expires_in", 7200))
    except (TypeError, ValueError):
        expires_in = 7200
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


# ── Loopback browser flow ──────────────────────────────────────────────────────

class _CallbackResult:
    __slots__ = ("code", "state", "error")

    def __init__(self) -> None:
        self.code: str = ""
        self.state: str = ""
        self.error: str = ""


def _make_handler(
    expected_state: str,
    result: _CallbackResult,
    done: threading.Event,
) -> type[http.server.BaseHTTPRequestHandler]:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(parsed.query)
            error = qs.get("error", [""])[0]
            code = qs.get("code", [""])[0]
            state = qs.get("state", [""])[0]
            if error:
                result.error = error
                self._respond(_ERROR_HTML.format(message="Access was denied."))
                done.set()
                return
            if not secrets.compare_digest(state, expected_state):
                result.error = "state_mismatch"
                self._respond(_ERROR_HTML.format(message="Login could not be verified (state mismatch)."))
                done.set()
                return
            result.code = code
            result.state = state
            self._respond(_SUCCESS_HTML)
            done.set()

        def _respond(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return  # silence default stderr access logging (never echo query params)

    return _Handler


def run_loopback_login(
    client: OAuthClient,
    *,
    open_browser: Callable[[str], bool] = webbrowser.open,
    transport: httpx.BaseTransport | None = None,
    timeout: float = CALLBACK_TIMEOUT,
    scopes: str = DEFAULT_SCOPES,
    print_url: Callable[[str], None] | None = None,
) -> TokenResponse:
    """Run the full browser authorization-code flow and return tokens.

    Binds an ephemeral loopback HTTP server, opens the authorize URL in the
    browser (always also surfaced via `print_url` as a fallback), waits for
    the callback (success/deny/timeout), then exchanges the code for tokens.
    """
    state = secrets.token_urlsafe(32)
    result = _CallbackResult()
    done = threading.Event()

    server: http.server.HTTPServer | None = None
    last_exc: OSError | None = None
    for _ in range(max(1, PORT_RETRIES)):
        try:
            handler_cls = _make_handler(state, result, done)
            server = http.server.HTTPServer(("localhost", 0), handler_cls)
            break
        except OSError as exc:
            last_exc = exc
            server = None
            continue
    if server is None:
        raise AuthError(f"could not bind loopback server: {last_exc}")

    port = server.server_address[1]
    redirect_uri = f"http://localhost:{port}/callback"
    authorize_url = build_authorize_url(client.client_id, redirect_uri, state, scopes=scopes)

    if print_url is not None:
        print_url(authorize_url)

    deadline = time.monotonic() + timeout

    def _serve() -> None:
        server.timeout = 0.5
        while not done.is_set() and time.monotonic() < deadline:
            server.handle_request()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    try:
        open_browser(authorize_url)
    except Exception:
        pass  # URL was already printed as a fallback; browser failure is not fatal

    thread.join(timeout=timeout + 1.0)
    server.server_close()

    if not done.is_set():
        raise AuthError("login timed out waiting for browser callback")
    if result.error:
        if result.error == "state_mismatch":
            raise AuthError("login failed: state mismatch (possible CSRF); try again")
        raise AuthError("login was denied or cancelled")
    if not result.code:
        raise AuthError("login callback did not include an authorization code")

    return exchange_code(client, result.code, redirect_uri, transport=transport)
