"""
status.py — Top-level dashboard: current user + pull requests awaiting review.

Inputs : current repo context (git remote or --repo override).
Outputs: authenticated user summary + table of PRs where the user is a reviewer.
Failure: ApiError on auth/API failures, ContextError when no repo can be resolved.
"""
from __future__ import annotations

from typing import Any

import typer

from bb.core.client import ApiClient, make_client
from bb.core.context import RepoContext, current_repo
from bb.core.output import print_table


def _make_client_for_ctx(ctx: RepoContext) -> ApiClient:
    return make_client(base_url=ctx.base_url) if ctx.base_url else make_client()


def _pr_row(p: dict[str, Any]) -> list[str]:
    pr_id = str(p.get("id", ""))
    title = str(p.get("title", ""))
    branch = str(p.get("source", {}).get("branch", {}).get("name", ""))
    author = str(p.get("author", {}).get("display_name", ""))
    state = str(p.get("state", ""))
    return [pr_id, title, branch, author, state]


def status(
    repo: str = typer.Option("", "--repo", "-R", help="workspace/slug"),
) -> None:
    """Show the authenticated user and pull requests awaiting your review."""
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
    me = client.get("/user")
    display_name = me.get("display_name", "")
    uuid = me.get("uuid", "")
    typer.echo(f"Logged in as {display_name}")
    typer.echo("")
    typer.echo("Reviewing")
    pr_base = f"/repositories/{ctx.workspace}/{ctx.slug}/pullrequests"
    items = list(
        client.paginate(pr_base, q=f'reviewers.uuid="{uuid}"', state="OPEN")
    )
    print_table(["ID", "TITLE", "BRANCH", "AUTHOR", "STATE"], [_pr_row(p) for p in items])
