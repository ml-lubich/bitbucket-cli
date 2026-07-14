"""Tests for bb.commands.browse gh-parity: TARGET (PR/file), -b/-c, -n/--no-browser."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def cloud_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_BASE_URL", "https://bitbucket.org")


def test_browse_pr_number_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "42", "--no-open"])
    assert "bitbucket.org/myws/myrepo/pull-requests/42" in result.output


def test_browse_pr_number_datacenter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_BASE_URL", raising=False)
    result = runner.invoke(
        app,
        [
            "browse",
            "42",
            "--repo",
            "https://bitbucket.polariswireless.com/scm/PVA/radio.git",
            "--no-open",
        ],
    )
    assert (
        "bitbucket.polariswireless.com/projects/PVA/repos/radio/pull-requests/42"
        in result.output
    )


def test_browse_file_path_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    monkeypatch.setattr("bb.commands.browse.current_branch", lambda: "main")
    result = runner.invoke(app, ["browse", "src/foo.py", "--no-open"])
    assert "bitbucket.org/myws/myrepo/src/main/src/foo.py" in result.output


def test_browse_file_path_datacenter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_BASE_URL", raising=False)
    monkeypatch.setattr("bb.commands.browse.current_branch", lambda: "main")
    result = runner.invoke(
        app,
        [
            "browse",
            "src/foo.py",
            "--repo",
            "https://bitbucket.polariswireless.com/scm/PVA/radio.git",
            "--no-open",
        ],
    )
    assert (
        "bitbucket.polariswireless.com/projects/PVA/repos/radio/browse/src/foo.py"
        "?at=refs/heads/main" in result.output
    )


def test_browse_file_path_with_explicit_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(
        app, ["browse", "src/foo.py", "--branch", "feature-x", "--no-open"]
    )
    assert "bitbucket.org/myws/myrepo/src/feature-x/src/foo.py" in result.output


def test_browse_branch_flag_source_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "-b", "feature-x", "--no-open"])
    assert "bitbucket.org/myws/myrepo/branch/feature-x" in result.output


def test_browse_commit_flag_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "-c", "abc1234", "--no-open"])
    assert "bitbucket.org/myws/myrepo/commits/abc1234" in result.output


def test_browse_commit_flag_datacenter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_BASE_URL", raising=False)
    result = runner.invoke(
        app,
        [
            "browse",
            "--commit",
            "abc1234",
            "--repo",
            "https://bitbucket.polariswireless.com/scm/PVA/radio.git",
            "--no-open",
        ],
    )
    assert (
        "bitbucket.polariswireless.com/projects/PVA/repos/radio/commits/abc1234"
        in result.output
    )


def test_browse_no_browser_flag_prints_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "--no-browser"])
    assert "bitbucket.org/myws/myrepo" in result.output


def test_browse_short_no_browser_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("bb.commands.browse.webbrowser.open", lambda url: opened.append(url))
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "-n"])
    assert len(opened) == 0
    assert "bitbucket.org/myws/myrepo" in result.output


def test_browse_bare_behavior_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "--no-open"])
    assert result.output.strip() == "https://bitbucket.org/myws/myrepo"


def test_browse_commit_takes_priority_over_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "-c", "abc123", "--no-open"])
    assert "commits/abc123" in result.output
