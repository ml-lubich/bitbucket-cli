"""Tests for bb.commands.browse — covers URL building and --no-open flag."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def cloud_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_BASE_URL", "https://bitbucket.org")


def test_browse_no_open_prints_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "--no-open"])
    assert "bitbucket.org/myws/myrepo" in result.output


def test_browse_no_open_with_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "myws/myrepo")
    result = runner.invoke(app, ["browse", "--branch", "feature-x", "--no-open"])
    assert "/branch/feature-x" in result.output


def test_browse_no_open_with_repo_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["browse", "--repo", "acme/api", "--no-open"])
    assert "bitbucket.org/acme/api" in result.output


def test_browse_datacenter_repo_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_BASE_URL", raising=False)
    result = runner.invoke(
        app,
        [
            "browse",
            "--repo",
            "https://bitbucket.polariswireless.com/scm/PVA/radio.git",
            "--no-open",
        ],
    )
    assert "bitbucket.polariswireless.com/projects/PVA/repos/radio" in result.output


def test_browse_url_contains_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "bigcorp/service")
    result = runner.invoke(app, ["browse", "--no-open"])
    assert "bigcorp" in result.output


def test_browse_url_contains_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "bigcorp/service")
    result = runner.invoke(app, ["browse", "--no-open"])
    assert "service" in result.output


def test_browse_does_not_open_browser_with_no_open(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("bb.commands.browse.webbrowser.open", lambda url: opened.append(url))
    monkeypatch.setenv("BB_REPO", "ws/r")
    runner.invoke(app, ["browse", "--no-open"])
    assert len(opened) == 0


def test_browse_opens_browser_without_no_open(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("bb.commands.browse.webbrowser.open", lambda url: opened.append(url))
    monkeypatch.setenv("BB_REPO", "ws/r")
    runner.invoke(app, ["browse"])
    assert len(opened) == 1


def test_browse_exit_code_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "ws/r")
    result = runner.invoke(app, ["browse", "--no-open"])
    assert result.exit_code == 0
