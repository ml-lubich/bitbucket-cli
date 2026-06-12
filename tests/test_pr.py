"""Tests for bb pr commands using CliRunner + monkeypatched make_client."""
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
_RESPONSES: dict[str, Any] = {}


def _fake_client(responses: dict[str, Any]) -> ApiClient:
    def handler(req: httpx.Request) -> httpx.Response:
        for path_fragment, body in responses.items():
            if path_fragment in req.url.path:
                return httpx.Response(200, content=json.dumps(body).encode(),
                                      headers={"content-type": "application/json"})
        return httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})
    return ApiClient(_CRED, transport=httpx.MockTransport(handler))


def _capturing_client(captured: list, response_body: dict, status: int = 200) -> ApiClient:
    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(status, content=json.dumps(response_body).encode(),
                              headers={"content-type": "application/json"})
    return ApiClient(_CRED, transport=httpx.MockTransport(handler))


_PR_LIST_RESP = {
    "values": [{
        "id": 42, "title": "My Feature PR",
        "source": {"branch": {"name": "feature/foo"}},
        "author": {"display_name": "alice"},
        "state": "OPEN",
    }]
}


def test_pr_list_shows_title(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client({"/pullrequests": _PR_LIST_RESP})
    monkeypatch.setattr("bb.commands.pr.make_client", lambda repo="": (client, _CTX))
    result = runner.invoke(app, ["pr", "list"])
    assert "My Feature PR" in result.output


def test_pr_create_posts_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []
    create_resp = {"id": 1, "links": {"html": {"href": "https://bb.org/pr/1"}}}
    client = _capturing_client(captured, create_resp)

    def fake_make(repo: str = "") -> tuple[ApiClient, RepoContext]:
        return client, _CTX

    monkeypatch.setattr("bb.commands.pr.make_client", fake_make)
    monkeypatch.setattr("bb.commands.pr.current_branch", lambda: "feature/x")
    monkeypatch.setattr("bb.commands.pr._repo_mainbranch", lambda c, ctx: "main")
    runner.invoke(app, ["pr", "create", "--title", "T", "--base", "main"])
    last = captured[-1]
    body = json.loads(last.content)
    assert body["destination"]["branch"]["name"] == "main"


def test_pr_merge_squash(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []
    client = _capturing_client(captured, {"id": 5})
    monkeypatch.setattr("bb.commands.pr.make_client", lambda repo="": (client, _CTX))
    runner.invoke(app, ["pr", "merge", "5", "--merge-strategy", "squash"])
    last = captured[-1]
    body = json.loads(last.content)
    assert body["merge_strategy"] == "squash"


def test_pr_review_approve(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []
    client = _capturing_client(captured, {})
    monkeypatch.setattr("bb.commands.pr.make_client", lambda repo="": (client, _CTX))
    runner.invoke(app, ["pr", "review", "7", "--approve"])
    assert any("/approve" in r.url.path for r in captured)


def test_pr_reopen_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client({})
    monkeypatch.setattr("bb.commands.pr.make_client", lambda repo="": (client, _CTX))
    result = runner.invoke(app, ["pr", "reopen", "1"])
    assert result.exit_code != 0


def test_pr_repo_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_ctx: list[RepoContext] = []

    def fake_make(repo: str = "") -> tuple[ApiClient, RepoContext]:
        ctx = RepoContext(repo.split("/")[0], repo.split("/")[1]) if "/" in repo else _CTX
        seen_ctx.append(ctx)
        client = _fake_client({"/pullrequests": _PR_LIST_RESP})
        return client, ctx

    monkeypatch.setattr("bb.commands.pr.make_client", fake_make)
    runner.invoke(app, ["pr", "list", "--repo", "ws2/slug2"])
    assert seen_ctx[0].workspace == "ws2"
