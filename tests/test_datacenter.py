"""Tests for Bitbucket Data Center deployment support."""
from __future__ import annotations

import json

import httpx

from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.core.deployment import deployment_from_base_url


def _dc_client(handler) -> ApiClient:
    deployment = deployment_from_base_url("https://bitbucket.polariswireless.com")
    return ApiClient(
        Credential(token="tok", host=deployment.host),
        deployment=deployment,
        transport=httpx.MockTransport(handler),
    )


def test_datacenter_repo_path_maps_to_projects_repos() -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        body = {
            "slug": "radio",
            "project": {"key": "PVA"},
            "public": False,
            "links": {"self": [{"href": "https://bitbucket.polariswireless.com/projects/PVA/repos/radio"}]},
        }
        return httpx.Response(200, content=json.dumps(body).encode())

    repo = _dc_client(handler).get("/repositories/PVA/radio")
    assert seen == ["/rest/api/1.0/projects/PVA/repos/radio"]
    assert repo["full_name"] == "PVA/radio"
    assert repo["is_private"] is True


def test_datacenter_pagination_uses_next_page_start() -> None:
    starts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        starts.append(req.url.params.get("start", "0"))
        body = {"values": [{"slug": f"r{len(starts)}", "project": {"key": "PVA"}}]}
        if len(starts) == 1:
            body["nextPageStart"] = 25
        return httpx.Response(200, content=json.dumps(body).encode())

    items = list(_dc_client(handler).paginate("/repositories/PVA"))
    assert starts == ["0", "25"]
    assert [item["full_name"] for item in items] == ["PVA/r1", "PVA/r2"]


def test_datacenter_pr_create_body_maps_refs() -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = json.loads(req.content)
        body = {
            "id": 12,
            "fromRef": {"displayId": "feature", "repository": {"slug": "radio", "project": {"key": "PVA"}}},
            "toRef": {"displayId": "main", "repository": {"slug": "radio", "project": {"key": "PVA"}}},
            "author": {"user": {"displayName": "Misha"}},
        }
        return httpx.Response(200, content=json.dumps(body).encode())

    payload = {
        "title": "Ship it",
        "source": {"branch": {"name": "feature"}},
        "destination": {"branch": {"name": "main"}},
        "description": "body",
    }
    pr = _dc_client(handler).post("/repositories/PVA/radio/pullrequests", json_body=payload)
    assert captured["fromRef"]["id"] == "refs/heads/feature"
    assert captured["toRef"]["repository"]["project"]["key"] == "PVA"
    assert pr["source"]["branch"]["name"] == "feature"


def test_datacenter_workspace_list_maps_project_key_to_slug() -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        body = {
            "values": [
                {"key": "PVA", "name": "Polaris Voice Analytics", "public": False},
                {"key": "CROWD", "name": "Crowd", "public": True},
            ]
        }
        return httpx.Response(200, content=json.dumps(body).encode())

    items = list(_dc_client(handler).paginate("/workspaces"))
    assert seen == ["/rest/api/1.0/projects"]
    assert [item["slug"] for item in items] == ["PVA", "CROWD"]
    assert [item["key"] for item in items] == ["PVA", "CROWD"]


def test_datacenter_workspace_view_maps_to_project() -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        body = {"key": "PVA", "name": "Polaris Voice Analytics", "public": False}
        return httpx.Response(200, content=json.dumps(body).encode())

    ws = _dc_client(handler).get("/workspaces/PVA")
    assert seen == ["/rest/api/1.0/projects/PVA"]
    assert ws["slug"] == "PVA"
    assert ws["links"]["html"]["href"].endswith("/projects/PVA")
