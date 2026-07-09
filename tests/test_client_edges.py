"""Edge coverage for ApiClient and Data Center mapping."""
from __future__ import annotations

import json

import httpx
import pytest

from bb.core.auth import Credential
from bb.core.client import (
    ApiClient,
    _map_datacenter_path,
    _normalize_datacenter_response,
    _strip_dc_api_prefix,
    raw_request,
)
from bb.core.deployment import deployment_from_base_url
from bb.core.errors import ApiError


def _cred() -> Credential:
    return Credential(token="tok", host="bitbucket.polariswireless.com")


def _deployment():
    return deployment_from_base_url("https://bitbucket.polariswireless.com")


def test_raw_request_with_base_url_maps_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod

    seen: list[str] = []
    monkeypatch.setattr(auth_mod, "resolve_credential", lambda host="bitbucket.org": _cred())

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        return httpx.Response(200, content=b"ok")

    text = raw_request(
        "GET",
        "/repositories/PVA/radio",
        base_url="https://bitbucket.polariswireless.com",
        transport=httpx.MockTransport(handler),
    )
    assert text == "ok" and seen == ["/rest/api/1.0/projects/PVA/repos/radio"]


def test_raw_request_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod

    monkeypatch.setattr(auth_mod, "resolve_credential", lambda host="bitbucket.org": _cred())
    transport = httpx.MockTransport(
        lambda req: httpx.Response(403, content=json.dumps({"message": "forbidden"}).encode())
    )
    with pytest.raises(ApiError):
        raw_request("GET", "/projects", base_url="https://bitbucket.polariswireless.com", transport=transport)


def test_strip_datacenter_api_prefix_latest() -> None:
    assert _strip_dc_api_prefix("/rest/api/latest/projects/PVA") == "/projects/PVA"


def test_map_datacenter_full_url_passthrough() -> None:
    assert _map_datacenter_path("https://example.com/rest/api/1.0/projects") == "https://example.com/rest/api/1.0/projects"


def test_normalize_datacenter_project_item() -> None:
    project = _normalize_datacenter_response(
        "/workspaces/ws/projects/PVA",
        {"key": "PVA", "public": False},
        "https://bitbucket.polariswireless.com",
    )
    assert project["links"]["html"]["href"].endswith("/projects/PVA")


def test_normalize_datacenter_branch_adds_target() -> None:
    data = _normalize_datacenter_response(
        "/repositories/PVA/radio/refs/branches",
        {"values": [{"displayId": "main", "latestCommit": "abcdef"}]},
        "https://bitbucket.polariswireless.com",
    )
    assert data["values"][0]["target"]["hash"] == "abcdef"


def test_delete_error_uses_datacenter_url() -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        return httpx.Response(404, content=b"missing")

    client = ApiClient(_cred(), deployment=_deployment(), transport=httpx.MockTransport(handler))
    with pytest.raises(ApiError):
        client.delete("/repositories/PVA/radio")
    assert seen == ["/rest/api/1.0/projects/PVA/repos/radio"]


def test_api_error_includes_method_path_and_hint() -> None:
    client = ApiClient(
        _cred(),
        deployment=_deployment(),
        transport=httpx.MockTransport(lambda req: httpx.Response(401, content=b"bad")),
    )
    with pytest.raises(ApiError) as exc_info:
        client.get("/repositories/PVA/radio")
    assert "GET /rest/api/1.0/projects/PVA/repos/radio" in str(exc_info.value)
