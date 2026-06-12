"""ctx.py — Compatibility shim for bb.core.context with legacy RepoRef API."""
from __future__ import annotations

from dataclasses import dataclass

from bb.core.context import RepoContext, resolve_repo, _parse_remote_url as _base_parse_remote_url
from bb.core.errors import ContextError

RepoContextError = ContextError
current_repo = resolve_repo


@dataclass(frozen=True)
class RepoRef:
    workspace: str
    slug: str

    @property
    def full_name(self) -> str:
        return f"{self.workspace}/{self.slug}"


def _parse_remote_url(url: str) -> RepoRef:
    ctx = _base_parse_remote_url(url)
    return RepoRef(workspace=ctx.workspace, slug=ctx.repo)


def parse_repo_arg(value: str) -> RepoRef:
    parts = value.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ContextError(f"expected workspace/repo, got: {value!r}")
    return RepoRef(workspace=parts[0], slug=parts[1])


__all__ = [
    "RepoContext", "RepoRef", "RepoContextError",
    "current_repo", "_parse_remote_url", "parse_repo_arg",
]
