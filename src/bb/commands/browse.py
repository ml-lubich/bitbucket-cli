"""
browse.py — Open a repository in the browser.
Inputs: optional --repo override, optional --branch/--commit, optional TARGET
        (PR number or file path).
Outputs: URL on stdout; webbrowser.open when --no-open/-n is not set.
Failure: ContextError when repo cannot be resolved.
"""
from __future__ import annotations

import webbrowser
from typing import Optional

import typer

from bb.core.config import load_settings
from bb.core.context import RepoContext, current_branch, current_repo, resolve_repo
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


def _build_pr_url(workspace: str, slug: str, pr_id: str, base_url: str = "") -> str:
    deployment = deployment_from_base_url(base_url or load_settings().base_url)
    if deployment.is_datacenter:
        return f"{deployment.web_url}/projects/{workspace}/repos/{slug}/pull-requests/{pr_id}"
    return f"{deployment.web_url}/{workspace}/{slug}/pull-requests/{pr_id}"


def _build_commit_url(workspace: str, slug: str, commit: str, base_url: str = "") -> str:
    deployment = deployment_from_base_url(base_url or load_settings().base_url)
    if deployment.is_datacenter:
        return f"{deployment.web_url}/projects/{workspace}/repos/{slug}/commits/{commit}"
    return f"{deployment.web_url}/{workspace}/{slug}/commits/{commit}"


def _build_file_url(
    workspace: str, slug: str, path: str, branch: Optional[str], base_url: str = ""
) -> str:
    resolved_branch = branch or current_branch()
    deployment = deployment_from_base_url(base_url or load_settings().base_url)
    if deployment.is_datacenter:
        base = f"{deployment.web_url}/projects/{workspace}/repos/{slug}/browse/{path}"
        return f"{base}?at=refs/heads/{resolved_branch}"
    return f"{deployment.web_url}/{workspace}/{slug}/src/{resolved_branch}/{path}"


def _resolve_ctx(repo: Optional[str]) -> RepoContext:
    if repo:
        return current_repo(override=repo)
    return resolve_repo()


@app.callback()
def browse(
    target: Optional[str] = typer.Argument(
        None, help="PR number or file path to open"
    ),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="workspace/slug override"),
    branch: Optional[str] = typer.Option(
        None, "--branch", "-b", help="Open the source tree at this branch"
    ),
    commit: Optional[str] = typer.Option(None, "--commit", "-c", help="Open this commit"),
    no_open: bool = typer.Option(
        False, "--no-open", "--no-browser", "-n", help="Print URL only, do not open browser"
    ),
) -> None:
    """Open the current repository in the browser."""
    ctx = _resolve_ctx(repo)
    if commit:
        url = _build_commit_url(ctx.workspace, ctx.slug, commit, ctx.base_url)
    elif target and target.isdigit():
        url = _build_pr_url(ctx.workspace, ctx.slug, target, ctx.base_url)
    elif target:
        url = _build_file_url(ctx.workspace, ctx.slug, target, branch, ctx.base_url)
    else:
        url = _build_url(ctx.workspace, ctx.slug, branch, ctx.base_url)
    typer.echo(url)
    if not no_open:
        webbrowser.open(url)


# backward-compat alias
browse_cmd = browse
