"""Tests for bb search commands."""
from __future__ import annotations

from typing import Callable

import httpx
import pytest
from typer.testing import CliRunner

from bb.cli import app
from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.core.context import RepoContext

runner = CliRunner()
_CRED = Credential(host="bitbucket.org", token="x", auth_type="bearer", username="")
_REPO = RepoContext(workspace="ws", slug="repo")


def _make_transport(handler: Callable) -> httpx.MockTransport:
    return httpx.MockTransport(handler)  # type: ignore[arg-type]


def _mock_client(responses: list[httpx.Response]) -> tuple[ApiClient, list[httpx.Request]]:
    idx = 0
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal idx
        captured.append(req)
        r = responses[idx]
        idx += 1
        return r

    return ApiClient(_CRED, transport=_make_transport(handler)), captured


def _patch(monkeypatch: pytest.MonkeyPatch, responses: list[httpx.Response]) -> list[httpx.Request]:
    client, captured = _mock_client(responses)
    monkeypatch.setattr("bb.commands.search.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.search.resolve_repo", lambda: _REPO)
    return captured


def test_search_repos_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    result = runner.invoke(app, ["search", "repos", "myrepo"])
    assert result.exit_code == 0


def test_search_repos_sends_name_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    runner.invoke(app, ["search", "repos", "foo"])
    assert captured[0].url.params["q"] == 'name~"foo"'
    assert str(captured[0].url.path).endswith("/repositories/ws")


def test_search_repos_shows_results(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = {"full_name": "ws/foo", "description": "desc", "is_private": True, "updated_on": "2026-01-01"}
    _patch(monkeypatch, [httpx.Response(200, json={"values": [repo]})])
    result = runner.invoke(app, ["search", "repos", "foo"])
    assert "ws/foo" in result.output


def test_search_repos_json(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = {"full_name": "ws/foo"}
    _patch(monkeypatch, [httpx.Response(200, json={"values": [repo]})])
    result = runner.invoke(app, ["search", "repos", "foo", "--json"])
    assert '"full_name"' in result.output


def test_search_repos_workspace_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    runner.invoke(app, ["search", "repos", "foo", "--workspace", "other"])
    assert str(captured[0].url.path).endswith("/repositories/other")


def test_search_code_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    result = runner.invoke(app, ["search", "code", "TODO"])
    assert result.exit_code == 0


def test_search_code_sends_search_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    runner.invoke(app, ["search", "code", "TODO"])
    assert captured[0].url.params["search_query"] == "TODO"
    assert str(captured[0].url.path).endswith("/workspaces/ws/search/code")


def test_search_code_shows_results(monkeypatch: pytest.MonkeyPatch) -> None:
    match = {"file": {"path": "src/foo.py"}, "content_match_count": 3}
    _patch(monkeypatch, [httpx.Response(200, json={"values": [match]})])
    result = runner.invoke(app, ["search", "code", "TODO"])
    assert "src/foo.py" in result.output


def test_search_code_empty_query_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [])
    result = runner.invoke(app, ["search", "code", ""])
    assert result.exit_code != 0


def test_search_help_exits_zero() -> None:
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
