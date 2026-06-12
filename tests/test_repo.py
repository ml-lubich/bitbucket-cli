"""Tests for bb.commands.repo — covers list, create, delete, set-default."""
from __future__ import annotations

from pathlib import Path
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
    client.delete.return_value = None
    return client


def _repo_fixture(full_name: str = "myws/myrepo") -> dict[str, Any]:
    return {
        "full_name": full_name,
        "description": "A test repo",
        "is_private": True,
        "updated_on": "2024-01-15T10:00:00.000000+00:00",
        "links": {"html": {"href": f"https://bitbucket.org/{full_name}"}},
    }


def test_repo_list_emits_full_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_repo_fixture("acme/backend")])
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    result = runner.invoke(app, ["repo", "list", "--workspace", "acme"])
    assert "acme/backend" in result.output


def test_repo_list_workspace_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_repo_fixture("envws/proj")])
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    monkeypatch.setenv("BB_REPO", "envws/something")
    result = runner.invoke(app, ["repo", "list"])
    assert "envws/proj" in result.output


def test_repo_list_json_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(paginate_returns=[_repo_fixture("ws/r")])
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    result = runner.invoke(app, ["repo", "list", "--workspace", "ws", "--json"])
    assert "full_name" in result.output


def test_repo_view_shows_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client(get_returns=_repo_fixture("ws/slug"))
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    result = runner.invoke(app, ["repo", "view", "ws/slug"])
    assert "ws/slug" in result.output


def test_repo_create_posts_is_private_true_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_post(path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.append(json_body or {})
        return {"full_name": "ws/newrepo", "links": {"html": {"href": "https://example.com"}}}

    client = _make_mock_client()
    client.post.side_effect = fake_post
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    monkeypatch.setenv("BB_REPO", "ws/x")
    runner.invoke(app, ["repo", "create", "--name", "newrepo"])
    assert captured[0].get("is_private") is True


def test_repo_create_public_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_post(path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.append(json_body or {})
        return {"full_name": "ws/pub", "links": {"html": {"href": "https://example.com"}}}

    client = _make_mock_client()
    client.post.side_effect = fake_post
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    monkeypatch.setenv("BB_REPO", "ws/x")
    runner.invoke(app, ["repo", "create", "--name", "pub", "--public"])
    assert captured[0].get("is_private") is False


def test_repo_delete_without_yes_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client()
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    runner.invoke(app, ["repo", "delete", "ws/todelete"], input="n\n")
    assert client.delete.call_count == 0


def test_repo_delete_with_yes_calls_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_mock_client()
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    runner.invoke(app, ["repo", "delete", "ws/todelete", "--yes"])
    assert client.delete.call_count == 1


def test_repo_set_default_writes_bb_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    def fake_toplevel(cmd: list[str], **kw: object) -> object:
        import subprocess
        r = subprocess.CompletedProcess(cmd, 0, stdout=str(tmp_path) + "\n", stderr="")
        return r

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_toplevel)
    runner.invoke(app, ["repo", "set-default", "myws/myrepo"])
    bb_toml = tmp_path / "bb.toml"
    assert bb_toml.exists()


def test_repo_set_default_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    import subprocess as sp

    def fake_run(cmd: list[str], **kw: object) -> sp.CompletedProcess[str]:
        return sp.CompletedProcess(cmd, 0, stdout=str(tmp_path) + "\n", stderr="")

    monkeypatch.setattr(sp, "run", fake_run)
    runner.invoke(app, ["repo", "set-default", "myws/myrepo"])
    content = (tmp_path / "bb.toml").read_text()
    assert "myws/myrepo" in content
