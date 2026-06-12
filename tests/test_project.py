"""Tests for bb.commands.project — covers list, view, create."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _make_mock_client(
    get_returns: dict[str, Any] | None = None,
    post_returns: dict[str, Any] | None = None,
    paginate_returns: list[dict[str, Any]] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.get.return_value = get_returns or {}
    client.post.return_value = post_returns or {}
    client.paginate.return_value = iter(paginate_returns or [])
    return client


def _proj_fixture(key: str = "PROJ", name: str = "My Project") -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": "A project",
        "is_private": True,
        "created_on": "2024-01-01T00:00:00.000000+00:00",
        "links": {"html": {"href": f"https://bitbucket.org/ws/projects/{key}"}},
    }


def test_project_list_emits_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_proj_fixture("BACKEND")])
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    result = runner.invoke(app, ["project", "list", "--workspace", "myws"])
    assert "BACKEND" in result.output


def test_project_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_proj_fixture("XYZ")])
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    result = runner.invoke(app, ["project", "list", "--workspace", "myws", "--json"])
    assert "key" in result.output


def test_project_view_shows_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(get_returns=_proj_fixture("TOOLS"))
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    result = runner.invoke(app, ["project", "view", "TOOLS", "--workspace", "myws"])
    assert "TOOLS" in result.output


def test_project_view_shows_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(get_returns=_proj_fixture("TOOLS"))
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    result = runner.invoke(app, ["project", "view", "TOOLS", "--workspace", "myws"])
    assert "bitbucket.org" in result.output


def test_project_create_posts_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_post(path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.append(json_body or {})
        return _proj_fixture("NEWPROJ")

    client = _make_mock_client()
    client.post.side_effect = fake_post
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    runner.invoke(
        app,
        ["project", "create", "--key", "NEWPROJ", "--name", "New Project", "--workspace", "ws"],
    )
    assert captured[0].get("key") == "NEWPROJ"


def test_project_create_private_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_post(path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.append(json_body or {})
        return _proj_fixture("PRIV")

    client = _make_mock_client()
    client.post.side_effect = fake_post
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    runner.invoke(
        app,
        ["project", "create", "--key", "PRIV", "--name", "Private Proj", "--workspace", "ws"],
    )
    assert captured[0].get("is_private") is True


def test_project_create_emits_key_in_output(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(post_returns=_proj_fixture("OUT"))
    monkeypatch.setattr("bb.commands.project.make_client", lambda: client)
    result = runner.invoke(
        app,
        ["project", "create", "--key", "OUT", "--name", "Output", "--workspace", "ws"],
    )
    assert "OUT" in result.output
