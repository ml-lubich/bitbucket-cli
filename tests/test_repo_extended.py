"""Additional repository command coverage."""
from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from bb.cli import app
from bb.core.errors import BBError

runner = CliRunner()


def _client() -> MagicMock:
    c = MagicMock()
    c.get.return_value = _repo()
    c.post.return_value = _repo("PVA/forked")
    c.delete.return_value = None
    c.paginate.return_value = iter([])
    return c


def _repo(full_name: str = "PVA/radio") -> dict:
    project, slug = full_name.split("/", 1)
    return {
        "full_name": full_name,
        "description": "repo",
        "is_private": True,
        "language": "python",
        "size": 10,
        "updated_on": "2026-01-01T00:00:00",
        "mainbranch": {"name": "main"},
        "links": {
            "html": {"href": f"https://bitbucket/projects/{project}/repos/{slug}"},
            "clone": [{"name": "https", "href": f"https://clone/{slug}.git"}],
        },
    }


def test_repo_clone_runs_git(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    calls: list[list[str]] = []
    monkeypatch.setenv("BB_TOKEN", "clone-tok")
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.repo._run_subprocess", lambda cmd: calls.append(cmd))
    runner.invoke(app, ["repo", "clone", "PVA/radio", "radio-copy"])
    assert calls == [
        [
            "git",
            "-c",
            "http.extraHeader=Authorization: Bearer clone-tok",
            "clone",
            "https://clone/radio.git",
            "radio-copy",
        ]
    ]


def test_repo_clone_ssh_skips_https_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.get.return_value = {
        **_repo(),
        "links": {
            "html": {"href": "https://bitbucket/projects/PVA/repos/radio"},
            "clone": [{"name": "ssh", "href": "git@bitbucket:PVA/radio.git"}],
        },
    }
    calls: list[list[str]] = []
    monkeypatch.setenv("BB_GIT_PROTOCOL", "ssh")
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.repo._run_subprocess", lambda cmd: calls.append(cmd))
    runner.invoke(app, ["repo", "clone", "PVA/radio"])
    assert calls == [["git", "clone", "git@bitbucket:PVA/radio.git"]]


def test_repo_clone_url_missing_protocol_raises() -> None:
    from bb.commands.repo import _clone_url

    with pytest.raises(BBError):
        _clone_url({"links": {"clone": []}}, "ssh")


def test_repo_fork_posts_to_forks(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    runner.invoke(app, ["repo", "fork", "PVA/radio", "--workspace", "OTHER"])
    assert client.post.call_args.args[0].endswith("/forks")


def test_repo_delete_with_datacenter_url_uses_context_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    seen: list[str] = []
    monkeypatch.setattr("bb.commands.repo.make_client", lambda base_url="": seen.append(base_url) or client)
    runner.invoke(
        app,
        ["repo", "delete", "https://bitbucket.polariswireless.com/scm/PVA/radio.git", "--yes"],
    )
    assert seen == ["https://bitbucket.polariswireless.com"]


def test_repo_sync_fetches_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.get.return_value = {
        **_repo(),
        "parent": _repo("PVA/base"),
        "mainbranch": {"name": "main"},
    }
    calls: list[list[str]] = []
    monkeypatch.setenv("BB_REPO", "PVA/radio")
    monkeypatch.setenv("BB_TOKEN", "sync-tok")
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.repo._run_subprocess", lambda cmd: calls.append(cmd))
    runner.invoke(app, ["repo", "sync"])
    assert calls[0] == [
        "git",
        "-c",
        "http.extraHeader=Authorization: Bearer sync-tok",
        "fetch",
        "https://clone/base.git",
        "main",
    ]


def test_repo_sync_without_parent_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setenv("BB_REPO", "PVA/radio")
    monkeypatch.setattr("bb.commands.repo.make_client", lambda: client)
    result = runner.invoke(app, ["repo", "sync"])
    assert result.exit_code != 0


def test_run_subprocess_raises_on_failure() -> None:
    from bb.commands.repo import _run_subprocess

    def fake_run(cmd: list[str], capture_output: bool, text: bool) -> CompletedProcess[str]:
        return CompletedProcess(cmd, 1, stdout="", stderr="bad")

    import bb.commands.repo as repo_mod

    original = repo_mod.subprocess.run
    repo_mod.subprocess.run = fake_run
    try:
        with pytest.raises(BBError):
            _run_subprocess(["git", "clone", "x"])
    finally:
        repo_mod.subprocess.run = original


def test_git_toplevel_falls_back_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bb.commands.repo import _git_toplevel

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "bb.commands.repo.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 1, stdout="", stderr=""),
    )
    assert _git_toplevel() == str(tmp_path)


def test_repo_edit_requires_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    result = runner.invoke(app, ["repo", "edit", "PVA/radio"])
    assert result.exit_code != 0
    assert isinstance(result.exception, BBError)
    client.put.assert_not_called()


def test_repo_edit_description_only(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.put.return_value = _repo()
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    result = runner.invoke(app, ["repo", "edit", "PVA/radio", "--description", "new desc"])
    assert result.exit_code == 0
    assert client.put.call_args.args[0] == "/repositories/PVA/radio"
    assert client.put.call_args.kwargs["json_body"] == {"description": "new desc"}


def test_repo_edit_private_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.put.return_value = _repo()
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    runner.invoke(app, ["repo", "edit", "PVA/radio", "--private"])
    assert client.put.call_args.kwargs["json_body"] == {"is_private": True}


def test_repo_edit_public_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.put.return_value = _repo()
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    runner.invoke(app, ["repo", "edit", "PVA/radio", "--public"])
    assert client.put.call_args.kwargs["json_body"] == {"is_private": False}


def test_repo_edit_project_and_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.put.return_value = _repo()
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    runner.invoke(
        app,
        ["repo", "edit", "PVA/radio", "--project", "PROJ", "--name", "new-name"],
    )
    assert client.put.call_args.kwargs["json_body"] == {
        "project": {"key": "PROJ"},
        "name": "new-name",
    }


def test_repo_edit_all_flags_combined(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.put.return_value = _repo()
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    runner.invoke(
        app,
        [
            "repo", "edit", "PVA/radio",
            "--description", "desc",
            "--private",
            "--project", "PROJ",
            "--name", "renamed",
        ],
    )
    assert client.put.call_args.kwargs["json_body"] == {
        "description": "desc",
        "is_private": True,
        "project": {"key": "PROJ"},
        "name": "renamed",
    }


def test_repo_edit_prints_updated_full_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.put.return_value = _repo("PVA/renamed")
    monkeypatch.setattr("bb.commands.repo._make_client_for_ctx", lambda ctx: client)
    result = runner.invoke(app, ["repo", "edit", "PVA/radio", "--name", "renamed"])
    assert "PVA/renamed" in result.output
