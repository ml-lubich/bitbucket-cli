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

from bb.core.config import load_settings
from bb.core.context import RepoContext, current_repo, resolve_repo
from bb.core.deployment import deployment_from_base_url

app = typer.Typer(help="Open Bitbucket in the browser", invoke_without_command=True)

def _build_url(workspace: str, slug: str, branch: Optional[str], base_url: str = "") -> str:
    deployment = deployment_from_base_url(base_url or load_settings().base_url)
    if deployment.is_datacenter:
        base = f"{deployment.web_url}/projects/{workspace}/repos/{slug}"
        if branch:
            return f"{base}/browse?at=refs/heads/{branch}"
        return base
    base = f"{deployment.web_url}/{workspace}/{slug}"
    if branch:
        return f"{base}/branch/{branch}"
    return base


def _resolve_ctx(repo: Optional[str]) -> RepoContext:
    if repo:
        return current_repo(override=repo)
    return resolve_repo()


@app.callback()
def browse(
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="workspace/slug override"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    no_open: bool = typer.Option(False, "--no-open", help="Print URL only, do not open browser"),
) -> None:
    """Open the current repository in the browser."""
    ctx = _resolve_ctx(repo)
    url = _build_url(ctx.workspace, ctx.slug, branch, ctx.base_url)
    typer.echo(url)
    if not no_open:
        webbrowser.open(url)


# backward-compat alias
browse_cmd = browse
