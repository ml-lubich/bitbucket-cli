"""
search.py — Search commands (repos, code) scoped to a workspace.

Inputs : workspace slug (--workspace or resolved from current repo), query string.
Outputs: table/JSON of matching repositories or code search results.
Failure: ApiError on 404/permission issues, BBError on missing workspace context.
"""
from __future__ import annotations

from typing import Any, Optional

import typer

from bb.core.client import ApiClient, make_client
from bb.core.context import resolve_repo
from bb.core.errors import BBError
from bb.core.output import print_json, print_table
from bb.core.validation import validate_limit

app = typer.Typer(help="Search Bitbucket")


def _resolve_ws(workspace: Optional[str]) -> str:
    if workspace:
        return workspace
    ctx = resolve_repo()
    return ctx.workspace


def _fmt_repo_row(r: dict[str, Any]) -> list[str]:
    desc = str(r.get("description") or "")
    return [
        str(r.get("full_name", "")),
        desc[:40],
        str(r.get("is_private", False)),
        str(r.get("updated_on", ""))[:10],
    ]


def _fmt_code_row(match: dict[str, Any]) -> list[str]:
    file_info = match.get("file") or {}
    path = str(file_info.get("path", ""))
    match_count = (match.get("content_match_count") or 0)
    return [path, str(match_count)]


@app.command("repos")
def search_repos(
    query: str = typer.Argument(..., help="Repository name to search for"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    limit: int = typer.Option(30, "--limit"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Search repositories by name within a workspace."""
    limit = validate_limit(limit)
    ws = _resolve_ws(workspace)
    client: ApiClient = make_client()
    items = list(
        client.paginate(f"/repositories/{ws}", q=f'name~"{query}"', pagelen=limit)
    )[:limit]
    if as_json:
        print_json(items)
        return
    print_table(["NAME", "DESCRIPTION", "PRIVATE", "UPDATED"], [_fmt_repo_row(r) for r in items])


@app.command("code")
def search_code(
    query: str = typer.Argument(..., help="Code search query"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    limit: int = typer.Option(30, "--limit"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Search code within a workspace."""
    if not query:
        raise BBError("search query must not be empty")
    limit = validate_limit(limit)
    ws = _resolve_ws(workspace)
    client: ApiClient = make_client()
    items = list(
        client.paginate(f"/workspaces/{ws}/search/code", search_query=query, pagelen=limit)
    )[:limit]
    if as_json:
        print_json(items)
        return
    print_table(["PATH", "MATCHES"], [_fmt_code_row(m) for m in items])
