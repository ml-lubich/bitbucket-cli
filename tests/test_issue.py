"""Tests for bb issue commands."""
from __future__ import annotations

import json
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


def _mock_client(responses: list[httpx.Response]) -> ApiClient:
    idx = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal idx
        r = responses[idx]
        idx += 1
        return r

    return ApiClient(_CRED, transport=_make_transport(handler))


def _patch(monkeypatch: pytest.MonkeyPatch, responses: list[httpx.Response]) -> ApiClient:
    client = _mock_client(responses)
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    return client


def test_issue_list_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    result = runner.invoke(app, ["issue", "list"])
    assert result.exit_code == 0


def test_issue_list_shows_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    issue = {"id": 1, "title": "Bug", "kind": "bug", "priority": "major", "state": "open"}
    _patch(monkeypatch, [httpx.Response(200, json={"values": [issue]})])
    result = runner.invoke(app, ["issue", "list"])
    assert "Bug" in result.output


def test_issue_view_shows_title(monkeypatch: pytest.MonkeyPatch) -> None:
    issue = {
        "id": 1, "title": "My Issue", "state": "open", "kind": "bug",
        "priority": "major", "reporter": {"display_name": "Alice"},
        "created_on": "2026-01-01", "content": {"raw": "body text"},
    }
    _patch(monkeypatch, [httpx.Response(200, json=issue)])
    result = runner.invoke(app, ["issue", "view", "1"])
    assert "My Issue" in result.output


def test_issue_create_posts_kind_and_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(201, json={"id": 42})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["issue", "create", "--title", "T", "--kind", "enhancement", "--priority", "critical"])
    body = json.loads(captured[0].content)
    assert body["kind"] == "enhancement" and body["priority"] == "critical"


def test_issue_create_prints_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(201, json={"id": 99})])
    result = runner.invoke(app, ["issue", "create", "--title", "X"])
    assert "99" in result.output


def test_issue_edit_no_flags_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [])
    result = runner.invoke(app, ["issue", "edit", "1"])
    assert result.exit_code != 0


def test_issue_close_puts_state_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json={})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["issue", "close", "5"])
    body = json.loads(captured[0].content)
    assert body["state"] == "resolved"


def test_issue_reopen_puts_state_open(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json={})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["issue", "reopen", "5"])
    body = json.loads(captured[0].content)
    assert body["state"] == "open"


def test_issue_comment_posts_content(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(201, json={})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["issue", "comment", "3", "--body", "hello"])
    body = json.loads(captured[0].content)
    assert body["content"]["raw"] == "hello"


def test_issue_delete_with_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(204)

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    result = runner.invoke(app, ["issue", "delete", "7", "--yes"])
    assert result.exit_code == 0


def test_issue_delete_prompts_without_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(204)])
    # CliRunner with no input causes abort → non-zero exit
    result = runner.invoke(app, ["issue", "delete", "7"])
    assert result.exit_code != 0


def test_issue_invalid_kind_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [])
    result = runner.invoke(app, ["issue", "create", "--title", "X", "--kind", "invalid"])
    assert result.exit_code != 0


def test_issue_invalid_priority_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [])
    result = runner.invoke(app, ["issue", "create", "--title", "X", "--priority", "extreme"])
    assert result.exit_code != 0


def test_issue_status_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        [
            httpx.Response(200, json={"uuid": "{u1}"}),
            httpx.Response(200, json={"values": []}),
            httpx.Response(200, json={"values": []}),
        ],
    )
    result = runner.invoke(app, ["issue", "status"])
    assert result.exit_code == 0


def test_issue_status_shows_reported_and_assigned(monkeypatch: pytest.MonkeyPatch) -> None:
    reported = {"id": 1, "title": "Reported issue", "kind": "bug", "priority": "major", "state": "open"}
    assigned = {"id": 2, "title": "Assigned issue", "kind": "bug", "priority": "minor", "state": "open"}
    _patch(
        monkeypatch,
        [
            httpx.Response(200, json={"uuid": "{u1}"}),
            httpx.Response(200, json={"values": [reported]}),
            httpx.Response(200, json={"values": [assigned]}),
        ],
    )
    result = runner.invoke(app, ["issue", "status"])
    assert "Reported issue" in result.output
    assert "Assigned issue" in result.output


def test_issue_status_queries_reporter_and_assignee_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        if str(req.url.path).endswith("/user"):
            return httpx.Response(200, json={"uuid": "{u1}"})
        return httpx.Response(200, json={"values": []})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.issue.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.issue.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["issue", "status"])
    assert str(captured[0].url.path).endswith("/user")
    assert captured[1].url.params["q"] == 'reporter.uuid="{u1}"'
    assert captured[2].url.params["q"] == 'assignee.uuid="{u1}"'
