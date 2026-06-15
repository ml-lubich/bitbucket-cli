"""Tests for make_client and raw_request in bb.core.client."""
from __future__ import annotations

import json

import httpx
import pytest

from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.core.errors import ApiError


def _cred(token: str = "tok") -> Credential:
    return Credential(token=token, source="test")


def _transport(status: int, body: str | dict | None = None) -> httpx.MockTransport:
    if isinstance(body, str):
        payload, ctype = body.encode(), "text/plain"
    else:
        payload, ctype = json.dumps(body or {}).encode(), "application/json"

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload, headers={"content-type": ctype})

    return httpx.MockTransport(handler)


def test_make_client_returns_api_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "resolve_credential", lambda **kw: _cred())
    import bb.core.client as client_mod
    client = client_mod.make_client()
    assert isinstance(client, ApiClient)


def test_raw_request_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "resolve_credential", lambda **kw: _cred())
    import bb.core.client as client_mod
    text = client_mod.raw_request("GET", "/user", transport=_transport(200, "hello world"))
    assert "hello world" in text


def test_raw_request_raises_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "resolve_credential", lambda **kw: _cred())
    import bb.core.client as client_mod
    transport = _transport(401, {"error": {"message": "bad token"}})
    with pytest.raises(ApiError) as exc_info:
        client_mod.raw_request("GET", "/user", transport=transport)
    assert exc_info.value.status_code == 401
