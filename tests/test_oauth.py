"""Tests for bb.core.oauth — authorize URL, exchange/refresh, loopback flow."""
from __future__ import annotations

import json
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest

from bb.core.errors import AuthError
from bb.core.oauth import (
    AUTHORIZE_URL,
    OAuthClient,
    TokenResponse,
    build_authorize_url,
    exchange_code,
    refresh_access_token,
    resolve_oauth_client,
    run_loopback_login,
)

# ── build_authorize_url ────────────────────────────────────────────────────────


def test_build_authorize_url_uses_authorize_endpoint() -> None:
    url = build_authorize_url("cid", "http://localhost:1234/callback", "state123")
    assert url.startswith(AUTHORIZE_URL)


def test_build_authorize_url_includes_required_params() -> None:
    url = build_authorize_url("cid", "http://localhost:1234/callback", "state123")
    qs = parse_qs(urlparse(url).query)
    assert qs["client_id"] == ["cid"]
    assert qs["response_type"] == ["code"]
    assert qs["redirect_uri"] == ["http://localhost:1234/callback"]
    assert qs["state"] == ["state123"]


def test_build_authorize_url_includes_scopes() -> None:
    url = build_authorize_url("cid", "http://localhost:1/callback", "s", scopes="account repository")
    qs = parse_qs(urlparse(url).query)
    assert qs["scope"] == ["account repository"]


def test_build_authorize_url_omits_scope_param_when_empty() -> None:
    url = build_authorize_url("cid", "http://localhost:1/callback", "s", scopes="")
    qs = parse_qs(urlparse(url).query)
    assert "scope" not in qs


# ── resolve_oauth_client ────────────────────────────────────────────────────────


def test_resolve_oauth_client_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_OAUTH_CLIENT_ID", "env-id")
    monkeypatch.setenv("BB_OAUTH_CLIENT_SECRET", "env-secret")
    client = resolve_oauth_client()
    assert client.client_id == "env-id"
    assert client.client_secret == "env-secret"


def test_resolve_oauth_client_from_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    import bb.core.config as cfg_mod

    monkeypatch.delenv("BB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("BB_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")  # type: ignore[operator]
    cfg_mod.set_user_value("oauth_client_id", "cfg-id")
    cfg_mod.set_user_value("oauth_client_secret", "cfg-secret")
    client = resolve_oauth_client()
    assert client.client_id == "cfg-id"
    assert client.client_secret == "cfg-secret"


def test_resolve_oauth_client_raises_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    import bb.core.config as cfg_mod
    import bb.core.oauth as oauth_mod

    monkeypatch.delenv("BB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("BB_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")  # type: ignore[operator]
    monkeypatch.setattr(oauth_mod, "_EMBEDDED_CLIENT_ID", "")
    monkeypatch.setattr(oauth_mod, "_EMBEDDED_CLIENT_SECRET", "")
    with pytest.raises(AuthError):
        resolve_oauth_client()


# ── exchange_code / refresh_access_token via MockTransport ─────────────────────


def _token_transport(status: int, body: dict | str) -> httpx.MockTransport:
    if isinstance(body, str):
        payload = body.encode()
        headers = {"content-type": "text/plain"}
    else:
        payload = json.dumps(body).encode()
        headers = {"content-type": "application/json"}

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload, headers=headers)

    return httpx.MockTransport(handler)


def test_exchange_code_returns_token_response() -> None:
    transport = _token_transport(
        200, {"access_token": "at", "refresh_token": "rt", "expires_in": 7200}
    )
    client = OAuthClient(client_id="cid", client_secret="secret")
    resp = exchange_code(client, "auth-code", "http://localhost:1/callback", transport=transport)
    assert resp == TokenResponse(access_token="at", refresh_token="rt", expires_in=7200)


def test_exchange_code_posts_grant_type_authorization_code() -> None:
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(parse_qs(req.content.decode()))
        return httpx.Response(
            200,
            content=json.dumps({"access_token": "at", "refresh_token": "rt", "expires_in": 100}).encode(),
            headers={"content-type": "application/json"},
        )

    client = OAuthClient(client_id="cid", client_secret="secret")
    exchange_code(client, "the-code", "http://localhost:1/callback", transport=httpx.MockTransport(handler))
    assert captured["grant_type"] == ["authorization_code"]
    assert captured["code"] == ["the-code"]


def test_exchange_code_uses_basic_auth_with_client_secret() -> None:
    captured_auth: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured_auth["authorization"] = req.headers.get("authorization", "")
        return httpx.Response(
            200,
            content=json.dumps({"access_token": "at", "refresh_token": "rt", "expires_in": 100}).encode(),
            headers={"content-type": "application/json"},
        )

    client = OAuthClient(client_id="myid", client_secret="mysecret")
    exchange_code(client, "code", "http://localhost:1/callback", transport=httpx.MockTransport(handler))
    assert captured_auth["authorization"].startswith("Basic ")


def test_refresh_access_token_posts_grant_type_refresh_token() -> None:
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(parse_qs(req.content.decode()))
        return httpx.Response(
            200,
            content=json.dumps({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 7200}).encode(),
            headers={"content-type": "application/json"},
        )

    client = OAuthClient(client_id="cid", client_secret="secret")
    resp = refresh_access_token(client, "old-refresh", transport=httpx.MockTransport(handler))
    assert captured["grant_type"] == ["refresh_token"]
    assert captured["refresh_token"] == ["old-refresh"]
    assert resp.access_token == "new-at"
    assert resp.refresh_token == "new-rt"


def test_exchange_code_non_2xx_raises_auth_error_without_body_leak() -> None:
    transport = _token_transport(400, {"error": "invalid_grant", "error_description": "SECRET_LEAK_MARKER"})
    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError) as excinfo:
        exchange_code(client, "bad-code", "http://localhost:1/callback", transport=transport)
    assert "SECRET_LEAK_MARKER" not in str(excinfo.value)


def test_refresh_non_2xx_raises_auth_error() -> None:
    transport = _token_transport(401, {"error": "invalid_grant"})
    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        refresh_access_token(client, "revoked", transport=transport)


def test_exchange_code_missing_access_token_raises() -> None:
    transport = _token_transport(200, {"refresh_token": "rt", "expires_in": 100})
    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        exchange_code(client, "code", "http://localhost:1/callback", transport=transport)


def test_exchange_code_defaults_expires_in_when_missing() -> None:
    transport = _token_transport(200, {"access_token": "at", "refresh_token": "rt"})
    client = OAuthClient(client_id="cid", client_secret="secret")
    resp = exchange_code(client, "code", "http://localhost:1/callback", transport=transport)
    assert resp.expires_in == 7200


def test_exchange_code_network_error_raises_auth_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=req)

    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        exchange_code(client, "code", "http://localhost:1/callback", transport=httpx.MockTransport(handler))


def test_exchange_code_invalid_json_raises_auth_error() -> None:
    transport = _token_transport(200, "not json{{{")
    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        exchange_code(client, "code", "http://localhost:1/callback", transport=transport)


# ── run_loopback_login ──────────────────────────────────────────────────────────


def _redirect_uri_from_authorize_url(authorize_url: str) -> str:
    """The authorize URL points at bitbucket.org; extract the loopback redirect_uri from it."""
    qs = parse_qs(urlparse(authorize_url).query)
    return qs["redirect_uri"][0]


def _hit_callback(authorize_url: str, params: dict[str, str]) -> None:
    """Simulate the browser hitting the loopback callback with the given query params."""
    redirect_uri = _redirect_uri_from_authorize_url(authorize_url)
    callback_url = f"{redirect_uri}?{urlencode(params)}"
    # Give the server thread a moment to start listening.
    time.sleep(0.05)
    httpx.get(callback_url, timeout=5)


def test_run_loopback_login_happy_path() -> None:
    captured_state: dict[str, str] = {}

    def fake_open_browser(url: str) -> bool:
        parsed_qs = parse_qs(urlparse(url).query)
        captured_state["state"] = parsed_qs["state"][0]
        threading.Thread(
            target=_hit_callback,
            args=(url, {"code": "the-auth-code", "state": parsed_qs["state"][0]}),
            daemon=True,
        ).start()
        return True

    transport = _token_transport(
        200, {"access_token": "at", "refresh_token": "rt", "expires_in": 7200}
    )
    client = OAuthClient(client_id="cid", client_secret="secret")
    resp = run_loopback_login(
        client, open_browser=fake_open_browser, transport=transport, timeout=5.0
    )
    assert resp.access_token == "at"
    assert resp.refresh_token == "rt"


def test_run_loopback_login_access_denied() -> None:
    def fake_open_browser(url: str) -> bool:
        parsed_qs = parse_qs(urlparse(url).query)
        threading.Thread(
            target=_hit_callback,
            args=(url, {"error": "access_denied", "state": parsed_qs["state"][0]}),
            daemon=True,
        ).start()
        return True

    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        run_loopback_login(client, open_browser=fake_open_browser, timeout=5.0)


def test_run_loopback_login_state_mismatch() -> None:
    def fake_open_browser(url: str) -> bool:
        threading.Thread(
            target=_hit_callback,
            args=(url, {"code": "some-code", "state": "wrong-state"}),
            daemon=True,
        ).start()
        return True

    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        run_loopback_login(client, open_browser=fake_open_browser, timeout=5.0)


def test_run_loopback_login_timeout() -> None:
    def fake_open_browser(url: str) -> bool:
        return True  # never hits the callback

    client = OAuthClient(client_id="cid", client_secret="secret")
    with pytest.raises(AuthError):
        run_loopback_login(client, open_browser=fake_open_browser, timeout=0.2)


def test_run_loopback_login_prints_url_even_when_browser_fails() -> None:
    printed: list[str] = []

    def failing_open_browser(url: str) -> bool:
        raise RuntimeError("no display")

    def fake_print(url: str) -> None:
        printed.append(url)
        # Simulate the user manually visiting the URL after seeing it printed.
        parsed_qs = parse_qs(urlparse(url).query)
        threading.Thread(
            target=_hit_callback,
            args=(url, {"code": "manual-code", "state": parsed_qs["state"][0]}),
            daemon=True,
        ).start()

    transport = _token_transport(
        200, {"access_token": "at", "refresh_token": "rt", "expires_in": 7200}
    )
    client = OAuthClient(client_id="cid", client_secret="secret")
    resp = run_loopback_login(
        client,
        open_browser=failing_open_browser,
        transport=transport,
        timeout=5.0,
        print_url=fake_print,
    )
    assert printed  # URL was surfaced despite browser-open failure
    assert resp.access_token == "at"


def test_run_loopback_login_uses_localhost_redirect_uri() -> None:
    seen_redirects: list[str] = []

    def fake_open_browser(url: str) -> bool:
        parsed_qs = parse_qs(urlparse(url).query)
        seen_redirects.append(parsed_qs["redirect_uri"][0])
        threading.Thread(
            target=_hit_callback,
            args=(url, {"code": "c", "state": parsed_qs["state"][0]}),
            daemon=True,
        ).start()
        return True

    transport = _token_transport(200, {"access_token": "at", "refresh_token": "rt", "expires_in": 100})
    client = OAuthClient(client_id="cid", client_secret="secret")
    run_loopback_login(client, open_browser=fake_open_browser, transport=transport, timeout=5.0)
    assert seen_redirects[0].startswith("http://localhost:")
    assert "127.0.0.1" not in seen_redirects[0]


def test_run_loopback_login_success_html_has_no_secrets() -> None:
    captured_html: dict[str, str] = {}

    def fake_open_browser(url: str) -> bool:
        parsed_qs = parse_qs(urlparse(url).query)
        redirect_uri = _redirect_uri_from_authorize_url(url)

        def _hit() -> None:
            time.sleep(0.05)
            resp = httpx.get(
                f"{redirect_uri}?"
                + urlencode({"code": "top-secret-code", "state": parsed_qs["state"][0]}),
                timeout=5,
            )
            captured_html["body"] = resp.text

        threading.Thread(target=_hit, daemon=True).start()
        return True

    transport = _token_transport(200, {"access_token": "at", "refresh_token": "rt", "expires_in": 100})
    client = OAuthClient(client_id="cid", client_secret="secret")
    run_loopback_login(client, open_browser=fake_open_browser, transport=transport, timeout=5.0)
    assert "top-secret-code" not in captured_html.get("body", "")
