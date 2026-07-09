"""Tests for bb.commands.workspace — covers list, view, members."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _make_mock_client(
    get_returns: dict[str, Any] | None = None,
    paginate_returns: list[dict[str, Any]] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.get.return_value = get_returns or {}
    client.paginate.return_value = iter(paginate_returns or [])
    return client


def _ws_fixture(slug: str = "myws") -> dict[str, Any]:
    return {
        "slug": slug,
        "name": f"My Workspace {slug}",
        "uuid": "{aaa-bbb-ccc}",
        "created_on": "2023-01-01T00:00:00.000000+00:00",
        "links": {"html": {"href": f"https://bitbucket.org/{slug}"}},
    }


def _member_fixture(display_name: str = "Alice", nickname: str = "alice") -> dict[str, Any]:
    return {
        "user": {
            "display_name": display_name,
            "nickname": nickname,
            "uuid": "{member-uuid}",
        }
    }


def test_workspace_list_emits_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_ws_fixture("acme")])
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "list"])
    assert "acme" in result.output


def test_workspace_list_emits_datacenter_project_key_as_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_mock_client(
        paginate_returns=[{"key": "PVA", "name": "Polaris Voice Analytics"}]
    )
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "list"])
    assert "PVA" in result.output


def test_workspace_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_ws_fixture("ws")])
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "list", "--json"])
    assert "slug" in result.output


def test_workspace_view_shows_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(get_returns=_ws_fixture("devteam"))
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "view", "devteam"])
    assert "devteam" in result.output


def test_workspace_view_shows_datacenter_key_as_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_mock_client(
        get_returns={
            "key": "PVA",
            "name": "Polaris Voice Analytics",
            "links": {
                "html": {
                    "href": "https://bitbucket.polariswireless.com/projects/PVA"
                }
            },
        }
    )
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "view", "PVA"])
    assert "slug:       PVA" in result.output


def test_workspace_view_shows_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(get_returns=_ws_fixture("devteam"))
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "view", "devteam"])
    assert "bitbucket.org/devteam" in result.output


def test_workspace_members_renders_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_member_fixture("Alice Smith", "alice")])
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "members", "myws"])
    assert "Alice Smith" in result.output


def test_workspace_members_renders_nickname(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_member_fixture("Bob Jones", "bjones")])
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "members", "myws"])
    assert "bjones" in result.output


def test_workspace_members_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_member_fixture("Carol", "carol")])
    monkeypatch.setattr("bb.commands.workspace.make_client", lambda: client)
    result = runner.invoke(app, ["workspace", "members", "myws", "--json"])
    assert "display_name" in result.output
