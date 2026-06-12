"""
context.py — Resolve workspace/repo/branch for the current directory.

Inputs : BB_REPO env var, override string, git remote origin URL.
Outputs: RepoContext(workspace, repo) with .full_name; current_branch().
Failure: ContextError with guidance when context cannot be determined.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from bb.core.errors import ContextError

_SSH_RE = re.compile(r"git@bitbucket\.org[:/]([^/]+)/([^/]+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"https?://(?:[^@]+@)?bitbucket\.org/([^/]+)/([^/]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class RepoContext:
    workspace: str
    slug: str

    @property
    def full_name(self) -> str:
        return f"{self.workspace}/{self.slug}"

    # legacy alias used by older command modules
    @property
    def repo(self) -> str:
        return self.slug


def current_repo(override: str = "") -> RepoContext:
    if override:
        return _parse_override(override)
    env_val = os.environ.get("BB_REPO", "")
    if env_val:
        return _parse_override(env_val)
    url = _git_remote_url()
    return _parse_remote_url(url)


def current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise ContextError("not inside a git repo") from exc


def resolve_repo() -> RepoContext:
    """Legacy alias used by test_context.py."""
    return current_repo()


def _parse_override(value: str) -> RepoContext:
    parts = value.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ContextError(f"invalid repo {value!r}; expected workspace/slug")
    return RepoContext(workspace=parts[0], slug=parts[1])


def _parse_ssh_url(url: str) -> RepoContext | None:
    m = _SSH_RE.match(url)
    if not m:
        return None
    return RepoContext(workspace=m.group(1), slug=m.group(2))


def _parse_https_url(url: str) -> RepoContext | None:
    m = _HTTPS_RE.match(url)
    if not m:
        return None
    return RepoContext(workspace=m.group(1), slug=m.group(2))


def _parse_remote_url(url: str) -> RepoContext:
    for parser in (_parse_ssh_url, _parse_https_url):
        result = parser(url)
        if result:
            return result
    raise ContextError(
        f"remote URL {url!r} is not a Bitbucket URL — "
        "pass BB_REPO=workspace/repo or use --repo"
    )


# Alias used by test_ctx.py
_parse_remote = _parse_remote_url


def _git_remote_url() -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise ContextError("not inside a git repo with an origin remote") from exc


# Compatibility aliases for tests that import from this module
_parse_remote = _parse_remote_url
