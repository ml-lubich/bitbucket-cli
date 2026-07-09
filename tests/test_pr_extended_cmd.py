"""Additional PR command coverage for gh-style workflows."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from bb.cli import app
from bb.core.context import RepoContext

runner = CliRunner()
_CTX = RepoContext("PVA", "radio", "https://bitbucket.polariswireless.com")


def _client() -> MagicMock:
    c = MagicMock()
    c.get.return_value = _pr()
    c.post.return_value = {"id": 9}
    c.put.return_value = {"id": 9}
    c.delete.return_value = None
    c.raw_get.return_value = "diff --git a/file b/file"
    c.paginate.return_value = iter([{"name": "build", "state": "SUCCESS", "url": "https://ci"}])
    return c


def _patch(monkeypatch: pytest.MonkeyPatch, client: MagicMock) -> None:
    monkeypatch.setattr("bb.commands.pr.make_client", lambda repo="": (client, _CTX))


def _pr() -> dict:
    return {
        "id": 9,
        "title": "Ship radio",
        "state": "OPEN",
        "author": {"display_name": "Misha"},
        "source": {
            "branch": {"name": "feature/radio"},
            "repository": {"links": {"clone": [{"name": "https", "href": "https://clone"}]}},
        },
        "destination": {"branch": {"name": "main"}},
        "created_on": "2026-01-01",
        "description": "body",
        "links": {"html": {"href": "https://bitbucket/pr/9"}},
    }


def test_pr_view_prints_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    result = runner.invoke(app, ["pr", "view", "9"])
    assert "Ship radio" in result.output


def test_pr_view_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    result = runner.invoke(app, ["pr", "view", "9", "--json"])
    assert '"title"' in result.output


def test_pr_view_web_opens_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    opened: list[str] = []
    _patch(monkeypatch, client)
    monkeypatch.setattr("bb.commands.pr.webbrowser.open", lambda url: opened.append(url))
    runner.invoke(app, ["pr", "view", "9", "--web"])
    assert opened == ["https://bitbucket/pr/9"]


def test_pr_checkout_fetches_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    calls: list[list[str]] = []
    _patch(monkeypatch, client)
    monkeypatch.setattr("bb.commands.pr.subprocess.run", lambda cmd, check: calls.append(cmd))
    runner.invoke(app, ["pr", "checkout", "9"])
    assert calls[0] == ["git", "fetch", "https://clone", "feature/radio"]


def test_pr_close_declines(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    runner.invoke(app, ["pr", "close", "9"])
    assert client.post.call_args.args[0].endswith("/9/decline")


def test_pr_edit_requires_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    result = runner.invoke(app, ["pr", "edit", "9"])
    assert result.exit_code != 0


def test_pr_edit_posts_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    runner.invoke(app, ["pr", "edit", "9", "--title", "New", "--base", "release"])
    assert client.put.call_args.kwargs["json_body"]["title"] == "New"


def test_pr_review_body_posts_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    runner.invoke(app, ["pr", "review", "9", "--approve", "--body", "ok"])
    paths = [call.args[0] for call in client.post.call_args_list]
    assert any(path.endswith("/comments") for path in paths)


def test_pr_review_rejects_multiple_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    result = runner.invoke(app, ["pr", "review", "9", "--approve", "--unapprove"])
    assert result.exit_code != 0


def test_pr_comment_posts_body(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    runner.invoke(app, ["pr", "comment", "9", "--body", "hello"])
    assert client.post.call_args.kwargs["json_body"]["content"]["raw"] == "hello"


def test_pr_diff_prints_text(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    result = runner.invoke(app, ["pr", "diff", "9"])
    assert "diff --git" in result.output


def test_pr_checks_prints_status(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _patch(monkeypatch, client)
    result = runner.invoke(app, ["pr", "checks", "9"])
    assert "build" in result.output
