"""Extended tests for ApiClient — put, delete, raw_get, basic-auth, raw_request."""
from __future__ import annotations

import json

import httpx
import pytest

from bb.core.auth import Credential
from bb.core.client import ApiClient, _BearerAuth, _build_auth
from bb.core.errors import ApiError


def _cred(token: str = "tok", username: str = "") -> Credential:
    return Credential(token=token, username=username, source="test")


def _transport(status: int, body: dict | str | None = None) -> httpx.MockTransport:
    if isinstance(body, str):
        payload = body.encode()
        content_type = "text/plain"
    else:
        payload = json.dumps(body or {}).encode()
        content_type = "application/json"

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


def test_put_returns_json() -> None:
    client = ApiClient(_cred(), transport=_transport(200, {"updated": True}))
    data = client.put("/repos/ws/r")
    assert data["updated"] is True


def test_delete_204_returns_none() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = ApiClient(_cred(), transport=httpx.MockTransport(handler))
    assert client.delete("/repos/ws/r") is None


def test_delete_error_raises_api_error() -> None:
    client = ApiClient(_cred(), transport=_transport(404, {"error": {"message": "not found"}}))
    with pytest.raises(ApiError):
        client.delete("/repos/ws/r")


def test_raw_get_returns_text() -> None:
    client = ApiClient(_cred(), transport=_transport(200, "raw text"))
    text = client.raw_get("/user")
    assert "raw text" in text


def test_build_auth_bearer_when_no_username() -> None:
    cred = _cred(token="abc")
    auth = _build_auth(cred)
    assert isinstance(auth, _BearerAuth)


def test_build_auth_basic_when_username_set() -> None:
    cred = _cred(token="abc", username="alice")
    auth = _build_auth(cred)
    assert isinstance(auth, httpx.BasicAuth)


def test_check_error_non_json_body() -> None:
    client = ApiClient(_cred(), transport=_transport(500, "Internal Server Error"))
    with pytest.raises(ApiError) as exc_info:
        client.get("/bad")
    assert exc_info.value.status_code == 500


def test_client_without_transport_creates_real_client() -> None:
    client = ApiClient(_cred())
    c = client._client()
    assert c is not None
