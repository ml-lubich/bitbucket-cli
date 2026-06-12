"""Tests for repository context resolution."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("url,expected_ws", [
    ("git@bitbucket.org:myws/myrepo.git", "myws"),
    ("git@bitbucket.org:myws/myrepo", "myws"),
    ("https://bitbucket.org/myws/myrepo.git", "myws"),
    ("https://user@bitbucket.org/myws/myrepo.git", "myws"),
    ("https://bitbucket.org/myws/myrepo", "myws"),
])
def test_parse_remote_url_workspace(url: str, expected_ws: str) -> None:
    from bb.core.context import _parse_remote_url
    ref = _parse_remote_url(url)
    assert ref is not None and ref.workspace == expected_ws


@pytest.mark.parametrize("url,expected_slug", [
    ("git@bitbucket.org:myws/myrepo.git", "myrepo"),
    ("https://bitbucket.org/myws/myrepo.git", "myrepo"),
])
def test_parse_remote_url_slug(url: str, expected_slug: str) -> None:
    from bb.core.context import _parse_remote_url
    ref = _parse_remote_url(url)
    assert ref is not None and ref.slug == expected_slug


def test_override_parses_correctly() -> None:
    from bb.core.context import current_repo
    ref = current_repo("myws/myrepo")
    assert ref.full_name == "myws/myrepo"


def test_bad_format_raises() -> None:
    from bb.core.context import ContextError, _parse_override
    with pytest.raises(ContextError):
        _parse_override("badformat")


def test_full_name_property() -> None:
    from bb.core.context import RepoContext
    ref = RepoContext(workspace="acme", slug="rocket")
    assert ref.full_name == "acme/rocket"
