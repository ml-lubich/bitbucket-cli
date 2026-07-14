"""Tests for the top-level bb status dashboard."""
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
    monkeypatch.setattr("bb.commands.status.make_client", lambda base_url="": client)
    monkeypatch.setattr("bb.commands.status.current_repo", lambda *_a, **_kw: _REPO)
    return captured


def test_status_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        [
            httpx.Response(200, json={"display_name": "Misha", "uuid": "{u1}"}),
            httpx.Response(200, json={"values": []}),
        ],
    )
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_status_shows_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        [
            httpx.Response(200, json={"display_name": "Misha", "uuid": "{u1}"}),
            httpx.Response(200, json={"values": []}),
        ],
    )
    result = runner.invoke(app, ["status"])
    assert "Misha" in result.output


def test_status_shows_reviewing_prs(monkeypatch: pytest.MonkeyPatch) -> None:
    pr = {
        "id": 5,
        "title": "Fix bug",
        "state": "OPEN",
        "author": {"display_name": "Alice"},
        "source": {"branch": {"name": "fix/bug"}},
    }
    _patch(
        monkeypatch,
        [
            httpx.Response(200, json={"display_name": "Misha", "uuid": "{u1}"}),
            httpx.Response(200, json={"values": [pr]}),
        ],
    )
    result = runner.invoke(app, ["status"])
    assert "Fix bug" in result.output


def test_status_queries_reviewer_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch(
        monkeypatch,
        [
            httpx.Response(200, json={"display_name": "Misha", "uuid": "{u1}"}),
            httpx.Response(200, json={"values": []}),
        ],
    )
    runner.invoke(app, ["status"])
    assert captured[1].url.params["q"] == 'reviewers.uuid="{u1}"'
    assert str(captured[0].url.path).endswith("/user")
    assert str(captured[1].url.path).endswith("/repositories/ws/repo/pullrequests")


def test_status_help_exits_zero() -> None:
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
