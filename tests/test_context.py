"""Tests for bb.core.context — URL parsing, env override, git remote resolution."""
from __future__ import annotations

import pytest

from bb.core.context import (
    RepoContext,
    _parse_https_url,
    _parse_override,
    _parse_remote_url,
    _parse_ssh_url,
    current_repo,
    resolve_repo,
)
from bb.core.errors import ContextError


@pytest.mark.parametrize("url,expected", [
    ("git@bitbucket.org:myws/myrepo.git", RepoContext("myws", "myrepo")),
    ("git@bitbucket.org:myws/myrepo", RepoContext("myws", "myrepo")),
])
def test_ssh_url_parsed(url: str, expected: RepoContext) -> None:
    assert _parse_ssh_url(url) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://bitbucket.org/myws/myrepo.git", RepoContext("myws", "myrepo")),
    ("https://bitbucket.org/myws/myrepo", RepoContext("myws", "myrepo")),
    ("https://user@bitbucket.org/myws/myrepo.git", RepoContext("myws", "myrepo")),
])
def test_https_url_parsed(url: str, expected: RepoContext) -> None:
    assert _parse_https_url(url) == expected


def test_ssh_url_non_bitbucket_returns_none() -> None:
    assert _parse_ssh_url("git@github.com:myws/myrepo.git") is None


def test_https_url_non_bitbucket_returns_none() -> None:
    assert _parse_https_url("https://github.com/myws/myrepo") is None


def test_datacenter_scm_https_url_parsed() -> None:
    ctx = _parse_https_url("https://bitbucket.polariswireless.com/scm/PVA/radio.git")
    assert ctx == RepoContext("PVA", "radio", "https://bitbucket.polariswireless.com")


def test_datacenter_project_web_url_parsed() -> None:
    ctx = _parse_https_url("https://bitbucket.polariswireless.com/projects/PVA/repos/radio/browse")
    assert ctx == RepoContext("PVA", "radio", "https://bitbucket.polariswireless.com")


def test_override_accepts_datacenter_url() -> None:
    ctx = current_repo("https://bitbucket.polariswireless.com/scm/PVA/radio.git")
    assert ctx.full_name == "PVA/radio"


@pytest.mark.parametrize("url,expected_ws", [
    ("git@bitbucket.org:myws/myrepo.git", "myws"),
    ("git@bitbucket.org:myws/myrepo", "myws"),
    ("https://bitbucket.org/myws/myrepo.git", "myws"),
    ("https://user@bitbucket.org/myws/myrepo.git", "myws"),
    ("https://bitbucket.org/myws/myrepo", "myws"),
])
def test_parse_remote_url_workspace(url: str, expected_ws: str) -> None:
    ref = _parse_remote_url(url)
    assert ref is not None and ref.workspace == expected_ws


@pytest.mark.parametrize("url,expected_slug", [
    ("git@bitbucket.org:myws/myrepo.git", "myrepo"),
    ("https://bitbucket.org/myws/myrepo.git", "myrepo"),
])
def test_parse_remote_url_slug(url: str, expected_slug: str) -> None:
    ref = _parse_remote_url(url)
    assert ref is not None and ref.slug == expected_slug


def test_override_parses_correctly() -> None:
    ref = current_repo("myws/myrepo")
    assert ref.full_name == "myws/myrepo"


def test_bad_format_raises_context_error() -> None:
    with pytest.raises(ContextError):
        _parse_override("badformat")


def test_full_name_property() -> None:
    ref = RepoContext(workspace="acme", slug="rocket")
    assert ref.full_name == "acme/rocket"


def test_bb_repo_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "envws/envrepo")
    ctx = resolve_repo()
    assert ctx == RepoContext("envws", "envrepo")


def test_bb_repo_env_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "envws/envrepo")
    assert resolve_repo().workspace == "envws"


def test_bb_repo_env_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "envws/envrepo")
    assert resolve_repo().repo == "envrepo"


def test_invalid_bb_repo_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "invalid-no-slash")
    with pytest.raises(ContextError):
        resolve_repo()


def test_no_remote_raises_context_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_REPO", raising=False)
    import subprocess

    def _fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(subprocess, "run", _fail)
    with pytest.raises(ContextError):
        resolve_repo()
