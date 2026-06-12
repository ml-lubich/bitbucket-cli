"""
browse.py — Open a repository in the browser.
Inputs: optional --repo override, optional --branch.
Outputs: URL on stdout; webbrowser.open when --no-open is not set.
Failure: ContextError when repo cannot be resolved.
"""
from __future__ import annotations

import webbrowser
from typing import Optional

import typer

from bb.core.context import resolve_repo
from bb.core.errors import BBError

app = typer.Typer(help="Open Bitbucket in the browser", invoke_without_command=True)

_BASE = "https://bitbucket.org"


def _build_url(workspace: str, slug: str, branch: Optional[str]) -> str:
    base = f"{_BASE}/{workspace}/{slug}"
    if branch:
        return f"{base}/branch/{branch}"
    return base


def _resolve_ws_slug(repo: Optional[str]) -> tuple[str, str]:
    if repo:
        parts = repo.split("/", 1)
        if len(parts) != 2:
            raise BBError(f"invalid repo format {repo!r}; expected workspace/slug")
        return parts[0], parts[1]
    ctx = resolve_repo()
    return ctx.workspace, ctx.slug


@app.callback()
def browse(
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="workspace/slug override"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    no_open: bool = typer.Option(False, "--no-open", help="Print URL only, do not open browser"),
) -> None:
    """Open the current repository in the browser."""
    workspace, slug = _resolve_ws_slug(repo)
    url = _build_url(workspace, slug, branch)
    typer.echo(url)
    if not no_open:
        webbrowser.open(url)


# backward-compat alias
browse_cmd = browse
