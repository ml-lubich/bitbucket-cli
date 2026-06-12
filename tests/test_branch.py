"""Tests for bb branch commands using CliRunner + monkeypatched make_client."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from bb.cli import app
from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.core.context import RepoContext

runner = CliRunner()
_CRED = Credential(token="testtoken", auth_type="bearer")
_CTX = RepoContext("ws", "slug")


def _fake_client(responses: dict[str, Any]) -> ApiClient:
    def handler(req: httpx.Request) -> httpx.Response:
        for frag, body in responses.items():
            if frag in req.url.path:
                code = 204 if req.method == "DELETE" else 200
                if code == 204:
                    return httpx.Response(204)
                return httpx.Response(200, content=json.dumps(body).encode(),
                                      headers={"content-type": "application/json"})
        code = 204 if req.method == "DELETE" else 200
        if code == 204:
            return httpx.Response(204)
        return httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})
    return ApiClient(_CRED, transport=httpx.MockTransport(handler))


def _capturing_client(captured: list, response_body: dict) -> ApiClient:
    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(201, content=json.dumps(response_body).encode(),
                              headers={"content-type": "application/json"})
    return ApiClient(_CRED, transport=httpx.MockTransport(handler))


_BRANCH_LIST_RESP = {
    "values": [{
        "name": "feature/cool",
        "target": {
            "hash": "abc1234567890",
            "author": {"user": {"display_name": "bob"}},
        },
    }]
}


def test_branch_list_shows_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client({"/refs/branches": _BRANCH_LIST_RESP})
    monkeypatch.setattr("bb.commands.branch.make_client", lambda repo="": (client, _CTX))
    result = runner.invoke(app, ["branch", "list"])
    assert "feature/cool" in result.output


def test_branch_create_posts_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    src_branch = {"target": {"hash": "deadbeef12345"}}
    responses = {"/refs/branches/main": src_branch}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        for frag, body in responses.items():
            if frag in req.url.path and req.method == "GET":
                return httpx.Response(200, content=json.dumps(body).encode(),
                                      headers={"content-type": "application/json"})
        return httpx.Response(201, content=b"{}", headers={"content-type": "application/json"})

    client = ApiClient(_CRED, transport=httpx.MockTransport(handler))
    monkeypatch.setattr("bb.commands.branch.make_client", lambda repo="": (client, _CTX))
    monkeypatch.setattr("bb.commands.branch._repo_mainbranch", lambda c, ctx: "main")
    runner.invoke(app, ["branch", "create", "new-branch", "--from", "main"])
    post_reqs = [r for r in captured if r.method == "POST"]
    assert len(post_reqs) >= 1
    body = json.loads(post_reqs[-1].content)
    assert body["target"]["hash"] == "deadbeef12345"


def test_branch_delete_confirms(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client({})
    monkeypatch.setattr("bb.commands.branch.make_client", lambda repo="": (client, _CTX))
    result = runner.invoke(app, ["branch", "delete", "old-branch"], input="y\n")
    assert result.exit_code == 0


def test_branch_delete_yes_skips_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client({})
    monkeypatch.setattr("bb.commands.branch.make_client", lambda repo="": (client, _CTX))
    result = runner.invoke(app, ["branch", "delete", "old-branch", "--yes"])
    assert result.exit_code == 0


def test_branch_repo_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_ctx: list[RepoContext] = []

    def fake_make(repo: str = "") -> tuple[ApiClient, RepoContext]:
        ctx = RepoContext(repo.split("/")[0], repo.split("/")[1]) if "/" in repo else _CTX
        seen_ctx.append(ctx)
        client = _fake_client({"/refs/branches": _BRANCH_LIST_RESP})
        return client, ctx

    monkeypatch.setattr("bb.commands.branch.make_client", fake_make)
    runner.invoke(app, ["branch", "list", "--repo", "ws3/repo3"])
    assert seen_ctx[0].workspace == "ws3"
