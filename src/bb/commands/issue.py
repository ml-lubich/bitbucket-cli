"""
issue.py — Bitbucket issue tracker commands.

Inputs:  --repo workspace/slug override, issue fields via CLI options.
Outputs: table/JSON for list; detail text for view; id for create.
Failure: ApiError on 404 (tracker disabled/not found), BBError on bad args.
"""
from __future__ import annotations

from typing import Annotated, Optional

import typer

from bb.core.client import make_client
from bb.core.context import RepoContext, current_repo
from bb.core.errors import BBError
from bb.core.output import print_json, print_table

app = typer.Typer(help="Manage issues")

_KINDS = {"bug", "enhancement", "proposal", "task"}
_PRIORITIES = {"trivial", "minor", "major", "critical", "blocker"}
_REPO_OPT = Annotated[str, typer.Option("--repo", "-R", help="workspace/slug")]


def _issues_path(repo: RepoContext) -> str:
    return f"/repositories/{repo.workspace}/{repo.slug}/issues"


def _fmt_row(issue: dict) -> list[str]:
    return [
        str(issue.get("id", "")),
        issue.get("title", ""),
        issue.get("kind", ""),
        issue.get("priority", ""),
        issue.get("state", ""),
    ]


def _print_detail(issue: dict) -> None:
    reporter = (issue.get("reporter") or {}).get("display_name", "")
    content = (issue.get("content") or {}).get("raw", "")
    typer.echo(f"Title:    {issue.get('title', '')}")
    typer.echo(f"State:    {issue.get('state', '')}")
    typer.echo(f"Kind:     {issue.get('kind', '')}")
    typer.echo(f"Priority: {issue.get('priority', '')}")
    typer.echo(f"Reporter: {reporter}")
    typer.echo(f"Created:  {issue.get('created_on', '')}")
    typer.echo(f"Body:\n{content}")


def _chk_kind(kind: str) -> None:
    if kind not in _KINDS:
        raise BBError(f"invalid kind {kind!r}; choose from {sorted(_KINDS)}")


def _chk_priority(priority: str) -> None:
    if priority not in _PRIORITIES:
        raise BBError(f"invalid priority {priority!r}; choose from {sorted(_PRIORITIES)}")


@app.command("list")
def issue_list(
    repo: _REPO_OPT = "",
    state: str = typer.Option("open", help="Filter by state"),
    limit: int = typer.Option(30, help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List issues."""
    client = make_client()
    ctx = current_repo(repo)
    items = list(
        client.paginate(_issues_path(ctx), q=f'state="{state}"', pagelen=str(limit))
    )[:limit]
    if as_json:
        print_json(items)
        return
    print_table(["ID", "TITLE", "KIND", "PRIORITY", "STATE"], [_fmt_row(i) for i in items])


@app.command("view")
def issue_view(
    issue_id: int = typer.Argument(..., help="Issue ID"),
    repo: _REPO_OPT = "",
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """View an issue."""
    client = make_client()
    ctx = current_repo(repo)
    issue = client.get(f"{_issues_path(ctx)}/{issue_id}")
    if as_json:
        print_json(issue)
        return
    _print_detail(issue)


@app.command("create")
def issue_create(
    repo: _REPO_OPT = "",
    title: str = typer.Option(..., "--title", help="Issue title"),
    body: str = typer.Option("", "--body", help="Issue body"),
    kind: str = typer.Option("bug", "--kind", help="bug|enhancement|proposal|task"),
    priority: str = typer.Option("major", "--priority", help="trivial|minor|major|critical|blocker"),
) -> None:
    """Create an issue."""
    _chk_kind(kind)
    _chk_priority(priority)
    client = make_client()
    ctx = current_repo(repo)
    payload: dict = {"title": title, "content": {"raw": body}, "kind": kind, "priority": priority}
    result = client.post(_issues_path(ctx), json_body=payload)
    typer.echo(str(result.get("id", "")))


@app.command("edit")
def issue_edit(
    issue_id: int = typer.Argument(..., help="Issue ID"),
    repo: _REPO_OPT = "",
    title: Optional[str] = typer.Option(None, "--title"),
    body: Optional[str] = typer.Option(None, "--body"),
    kind: Optional[str] = typer.Option(None, "--kind"),
    priority: Optional[str] = typer.Option(None, "--priority"),
) -> None:
    """Edit an issue."""
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["content"] = {"raw": body}
    if kind is not None:
        _chk_kind(kind)
        payload["kind"] = kind
    if priority is not None:
        _chk_priority(priority)
        payload["priority"] = priority
    if not payload:
        raise BBError("provide at least one of --title, --body, --kind, --priority")
    client = make_client()
    ctx = current_repo(repo)
    client.put(f"{_issues_path(ctx)}/{issue_id}", json_body=payload)


@app.command("close")
def issue_close(
    issue_id: int = typer.Argument(..., help="Issue ID"),
    repo: _REPO_OPT = "",
) -> None:
    """Close an issue (sets state to resolved)."""
    client = make_client()
    ctx = current_repo(repo)
    client.put(f"{_issues_path(ctx)}/{issue_id}", json_body={"state": "resolved"})


@app.command("reopen")
def issue_reopen(
    issue_id: int = typer.Argument(..., help="Issue ID"),
    repo: _REPO_OPT = "",
) -> None:
    """Reopen an issue (sets state to open)."""
    client = make_client()
    ctx = current_repo(repo)
    client.put(f"{_issues_path(ctx)}/{issue_id}", json_body={"state": "open"})


@app.command("comment")
def issue_comment(
    issue_id: int = typer.Argument(..., help="Issue ID"),
    repo: _REPO_OPT = "",
    body: str = typer.Option(..., "--body", help="Comment body"),
) -> None:
    """Add a comment to an issue."""
    client = make_client()
    ctx = current_repo(repo)
    client.post(f"{_issues_path(ctx)}/{issue_id}/comments", json_body={"content": {"raw": body}})


@app.command("delete")
def issue_delete(
    issue_id: int = typer.Argument(..., help="Issue ID"),
    repo: _REPO_OPT = "",
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete an issue."""
    if not yes:
        typer.confirm(f"Delete issue #{issue_id}?", abort=True)
    client = make_client()
    ctx = current_repo(repo)
    client.delete(f"{_issues_path(ctx)}/{issue_id}")
