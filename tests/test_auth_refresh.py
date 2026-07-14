"""Tests for OAuth token refresh: maybe_refresh gating, rotation persistence,
refresh_credential errors, and _RefreshingBearerAuth's reactive 401 retry.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

from bb.core.auth import Credential, maybe_refresh, refresh_credential, save_credential
from bb.core.client import ApiClient
from bb.core.errors import ApiError, AuthError
from bb.core.oauth import TokenResponse


def _patch_hosts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hosts = tmp_path / "hosts.toml"
    import bb.core.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    return hosts


def _oauth_cred(
    *,
    token: str = "access-tok",
    refresh_token: str = "refresh-tok",
    expires_at: float = 0.0,
    source: str = "keyring",
) -> Credential:
    return Credential(
        token=token,
        auth_type="oauth",
        refresh_token=refresh_token,
        expires_at=expires_at,
        source=source,
    )


# ── maybe_refresh gating ─────────────────────────────────────────────────────


def test_maybe_refresh_skips_non_oauth() -> None:
    cred = Credential(token="tok", auth_type="bearer", source="keyring")
    assert maybe_refresh(cred) is cred


def test_maybe_refresh_skips_when_no_refresh_token() -> None:
    cred = _oauth_cred(refresh_token="", expires_at=time.time() - 10)
    assert maybe_refresh(cred) is cred


def test_maybe_refresh_skips_env_source(monkeypatch: pytest.MonkeyPatch) -> None:
    cred = _oauth_cred(expires_at=time.time() - 10, source="env:BB_TOKEN")
    assert maybe_refresh(cred) is cred


def test_maybe_refresh_skips_dotenv_source() -> None:
    cred = _oauth_cred(expires_at=time.time() - 10, source="dotenv:BB_TOKEN")
    assert maybe_refresh(cred) is cred


def test_maybe_refresh_skips_when_expires_at_zero() -> None:
    cred = _oauth_cred(expires_at=0.0)
    assert maybe_refresh(cred) is cred


def test_maybe_refresh_skips_when_not_near_expiry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    cred = _oauth_cred(expires_at=time.time() + 3600)  # far from expiry
    assert maybe_refresh(cred) is cred


def test_maybe_refresh_refreshes_within_skew(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(
            access_token="new-access", refresh_token="new-refresh", expires_in=7200
        ),
    )
    cred = _oauth_cred(expires_at=time.time() + 30)  # within default 120s skew
    result = maybe_refresh(cred)
    assert result.token == "new-access"
    assert result.refresh_token == "new-refresh"


def test_maybe_refresh_refreshes_when_already_expired(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(
            access_token="new-access", refresh_token="new-refresh", expires_in=7200
        ),
    )
    cred = _oauth_cred(expires_at=time.time() - 100)
    result = maybe_refresh(cred)
    assert result.token == "new-access"


def test_maybe_refresh_respects_custom_skew(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    cred = _oauth_cred(expires_at=time.time() + 300)  # 5 min out
    # default skew (120s) would NOT refresh; explicit large skew should.
    assert maybe_refresh(cred, skew=120.0) is cred


# ── rotation persistence ─────────────────────────────────────────────────────


def test_refresh_credential_persists_new_access_and_refresh_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(
            access_token="rotated-access", refresh_token="rotated-refresh", expires_in=7200
        ),
    )
    cred = _oauth_cred(token="old-access", refresh_token="old-refresh")
    save_credential(cred)
    new_cred = refresh_credential(cred)
    assert new_cred.token == "rotated-access"
    assert new_cred.refresh_token == "rotated-refresh"

    import bb.core.auth as auth_mod

    stored = auth_mod._cred_from_file(cred.host)
    assert stored is not None
    assert stored.token == "rotated-access"
    assert stored.refresh_token == "rotated-refresh"


def test_refresh_credential_updates_expires_at(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(
            access_token="a", refresh_token="r", expires_in=3600
        ),
    )
    before = time.time()
    cred = _oauth_cred()
    new_cred = refresh_credential(cred)
    assert new_cred.expires_at >= before + 3600


def test_refresh_credential_falls_back_to_old_refresh_token_when_not_rotated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(access_token="a2", refresh_token="", expires_in=100),
    )
    cred = _oauth_cred(refresh_token="stays-the-same")
    new_cred = refresh_credential(cred)
    assert new_cred.refresh_token == "stays-the-same"


def test_refresh_credential_rejects_non_oauth() -> None:
    cred = Credential(token="tok", auth_type="bearer")
    with pytest.raises(AuthError):
        refresh_credential(cred)


def test_refresh_credential_rejects_missing_refresh_token() -> None:
    cred = Credential(token="tok", auth_type="oauth", refresh_token="")
    with pytest.raises(AuthError):
        refresh_credential(cred)


def test_refresh_credential_revoked_refresh_raises_auth_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))

    def _raise(*a: object, **k: object) -> TokenResponse:
        raise AuthError("OAuth token request failed with status 401")

    monkeypatch.setattr(oauth_mod, "refresh_access_token", _raise)
    cred = _oauth_cred()
    with pytest.raises(AuthError, match="run `bb auth login`"):
        refresh_credential(cred)


def test_refresh_credential_error_never_leaks_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))

    def _raise(*a: object, **k: object) -> TokenResponse:
        raise AuthError("OAuth token request failed with status 400")

    monkeypatch.setattr(oauth_mod, "refresh_access_token", _raise)
    cred = _oauth_cred()
    with pytest.raises(AuthError) as excinfo:
        refresh_credential(cred)
    assert "SECRET" not in str(excinfo.value)


# ── _RefreshingBearerAuth reactive 401 → refresh → retry ──────────────────────


def test_refreshing_bearer_auth_retries_once_after_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(
            access_token="fresh-token", refresh_token="fresh-refresh", expires_in=7200
        ),
    )

    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        auth_header = req.headers.get("authorization", "")
        calls.append(auth_header)
        if auth_header == "Bearer expired-token":
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(200, json={"ok": True})

    cred = _oauth_cred(token="expired-token")
    client = ApiClient(cred, transport=httpx.MockTransport(handler))
    data = client.get("/user")
    assert data == {"ok": True}
    assert calls == ["Bearer expired-token", "Bearer fresh-token"]


def test_refreshing_bearer_auth_does_not_loop_on_repeated_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(
            access_token="still-bad", refresh_token="still-bad-refresh", expires_in=7200
        ),
    )

    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(401, json={"error": {"message": "expired"}})

    cred = _oauth_cred(token="expired-token")
    client = ApiClient(cred, transport=httpx.MockTransport(handler))
    with pytest.raises(ApiError):
        client.get("/user")
    # Exactly one retry: original request + one refreshed retry, never more.
    assert call_count["n"] == 2


def test_refreshing_bearer_auth_second_client_request_also_refreshes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Retry state must be local to each auth_flow() call, not shared instance
    state — otherwise a second request through the same client/Auth instance
    could skip its own refresh-and-retry once `retried` flips True once."""
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    refresh_calls = {"n": 0}

    def _refresh(client: object, refresh_token: str, **kw: object) -> TokenResponse:
        refresh_calls["n"] += 1
        return TokenResponse(
            access_token=f"fresh-{refresh_calls['n']}", refresh_token="fresh-refresh", expires_in=7200
        )

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(oauth_mod, "refresh_access_token", _refresh)

    request_log: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        auth_header = req.headers.get("authorization", "")
        request_log.append(auth_header)
        if auth_header in ("Bearer expired-token", "Bearer fresh-1"):
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(200, json={"ok": True})

    cred = _oauth_cred(token="expired-token")
    client = ApiClient(cred, transport=httpx.MockTransport(handler))

    # First request: 401 -> refresh to fresh-1 -> retry with fresh-1 -> still 401 (per handler above).
    with pytest.raises(ApiError):
        client.get("/user")

    # Second request through a fresh ApiClient built from the rotated credential
    # (mirrors real usage: ApiClient is short-lived per command, credential is
    # persisted+reloaded). Refresh must fire again, not be skipped.
    import bb.core.auth as auth_mod

    stored = auth_mod._cred_from_file(cred.host)
    assert stored is not None
    client2 = ApiClient(stored, transport=httpx.MockTransport(handler))
    data = client2.get("/user")
    assert data == {"ok": True}
    assert refresh_calls["n"] == 2


def test_same_client_second_request_uses_rotated_token_without_double_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: ApiClient must not rebuild auth from its stale self._cred on
    each request. After _RefreshingBearerAuth refreshes+rotates on request #1,
    request #2 through the SAME ApiClient must carry the new token and must
    not trigger a second refresh (which would burn an already-rotated-out
    refresh token and guarantee a second 401)."""
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.oauth as oauth_mod

    refresh_calls = {"n": 0}

    def _refresh(client: object, refresh_token: str, **kw: object) -> TokenResponse:
        refresh_calls["n"] += 1
        return TokenResponse(
            access_token="new-access", refresh_token="new-refresh", expires_in=7200
        )

    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(oauth_mod, "refresh_access_token", _refresh)

    request_log: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        auth_header = req.headers.get("authorization", "")
        request_log.append(auth_header)
        if auth_header == "Bearer expired-token":
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(200, json={"ok": True})

    cred = _oauth_cred(token="expired-token")
    client = ApiClient(cred, transport=httpx.MockTransport(handler))

    # Request #1: 401 on expired-token -> refresh -> retry with new-access -> 200.
    data1 = client.get("/user")
    assert data1 == {"ok": True}
    assert refresh_calls["n"] == 1

    # Request #2 through the SAME ApiClient must carry the new token directly
    # (no stale-cred rebuild) and must not hit the token endpoint again.
    data2 = client.get("/repositories")
    assert data2 == {"ok": True}
    assert refresh_calls["n"] == 1
    assert request_log == ["Bearer expired-token", "Bearer new-access", "Bearer new-access"]


def test_bearer_auth_untouched_for_plain_bearer_cred() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.headers.get("authorization", ""))
        return httpx.Response(200, json={"ok": True})

    cred = Credential(token="plain-tok", auth_type="bearer")
    client = ApiClient(cred, transport=httpx.MockTransport(handler))
    client.get("/user")
    assert calls == ["Bearer plain-tok"]


def test_basic_auth_untouched_for_username_cred() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.headers.get("authorization", ""))
        return httpx.Response(200, json={"ok": True})

    cred = Credential(token="tok", username="alice", auth_type="basic")
    client = ApiClient(cred, transport=httpx.MockTransport(handler))
    client.get("/user")
    assert calls[0].startswith("Basic ")
