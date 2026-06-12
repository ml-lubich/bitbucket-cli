"""Tests for bb.core.ctx compatibility shim."""
from __future__ import annotations

import pytest


def test_reporef_full_name() -> None:
    from bb.core.ctx import RepoRef
    ref = RepoRef(workspace="acme", slug="api")
    assert ref.full_name == "acme/api"


def test_reporef_workspace() -> None:
    from bb.core.ctx import RepoRef
    ref = RepoRef(workspace="ws", slug="r")
    assert ref.workspace == "ws"


def test_reporef_slug() -> None:
    from bb.core.ctx import RepoRef
    ref = RepoRef(workspace="ws", slug="r")
    assert ref.slug == "r"


def test_parse_remote_url_returns_reporef() -> None:
    from bb.core.ctx import RepoRef, _parse_remote_url
    ref = _parse_remote_url("git@bitbucket.org:myws/myrepo.git")
    assert isinstance(ref, RepoRef)


def test_parse_remote_url_workspace() -> None:
    from bb.core.ctx import _parse_remote_url
    ref = _parse_remote_url("https://bitbucket.org/myws/myrepo.git")
    assert ref.workspace == "myws"


def test_parse_remote_url_slug() -> None:
    from bb.core.ctx import _parse_remote_url
    ref = _parse_remote_url("https://bitbucket.org/myws/myrepo")
    assert ref.slug == "myrepo"


def test_parse_repo_arg_splits_correctly() -> None:
    from bb.core.ctx import parse_repo_arg
    ref = parse_repo_arg("corp/backend")
    assert ref.workspace == "corp"
    assert ref.slug == "backend"


def test_parse_repo_arg_full_name() -> None:
    from bb.core.ctx import parse_repo_arg
    ref = parse_repo_arg("corp/backend")
    assert ref.full_name == "corp/backend"


def test_parse_repo_arg_bad_format_raises() -> None:
    from bb.core.ctx import RepoContextError, parse_repo_arg
    with pytest.raises(RepoContextError):
        parse_repo_arg("no-slash")


def test_repo_context_error_is_context_error() -> None:
    from bb.core.ctx import RepoContextError
    from bb.core.errors import ContextError
    assert RepoContextError is ContextError


def test_current_repo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_REPO", "ctx/repo")
    from bb.core.ctx import current_repo
    ref = current_repo()
    assert ref.workspace == "ctx"
