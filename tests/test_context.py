from __future__ import annotations

import pytest

from bb.core.context import RepoContext, resolve_repo, _parse_ssh_url, _parse_https_url
from bb.core.errors import ContextError


@pytest.mark.parametrize("url,expected", [
    ("git@bitbucket.org:myws/myrepo.git", RepoContext("myws", "myrepo")),
    ("git@bitbucket.org:myws/myrepo", RepoContext("myws", "myrepo")),
])
def test_ssh_url_parsed(url: str, expected: RepoContext):
    assert _parse_ssh_url(url) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://bitbucket.org/myws/myrepo.git", RepoContext("myws", "myrepo")),
    ("https://bitbucket.org/myws/myrepo", RepoContext("myws", "myrepo")),
    ("https://user@bitbucket.org/myws/myrepo.git", RepoContext("myws", "myrepo")),
])
def test_https_url_parsed(url: str, expected: RepoContext):
    assert _parse_https_url(url) == expected


def test_ssh_url_non_bitbucket_returns_none():
    result = _parse_ssh_url("git@github.com:myws/myrepo.git")
    assert result is None


def test_https_url_non_bitbucket_returns_none():
    result = _parse_https_url("https://github.com/myws/myrepo")
    assert result is None


def test_bb_repo_env_wins(monkeypatch):
    monkeypatch.setenv("BB_REPO", "envws/envrepo")
    ctx = resolve_repo()
    assert ctx == RepoContext("envws", "envrepo")


def test_bb_repo_env_workspace(monkeypatch):
    monkeypatch.setenv("BB_REPO", "envws/envrepo")
    ctx = resolve_repo()
    assert ctx.workspace == "envws"


def test_bb_repo_env_repo(monkeypatch):
    monkeypatch.setenv("BB_REPO", "envws/envrepo")
    ctx = resolve_repo()
    assert ctx.repo == "envrepo"


def test_invalid_bb_repo_env_raises(monkeypatch):
    monkeypatch.setenv("BB_REPO", "invalid-no-slash")
    with pytest.raises(ContextError):
        resolve_repo()


def test_no_remote_raises_context_error(monkeypatch):
    monkeypatch.delenv("BB_REPO", raising=False)
    import subprocess
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")
    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(ContextError):
        resolve_repo()
