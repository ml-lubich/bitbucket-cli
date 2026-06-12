"""
snippet.py — Bitbucket Snippets commands.

Inputs:  workspace + snippet id from CLI; --file path for create.
Outputs: table/JSON for list; detail text for view; raw file content.
Failure: BBError when file missing or no fields provided; ApiError on HTTP errors.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from bb.core.client import make_client, post_files, raw_request
from bb.core.errors import BBError
from bb.core.out import print_json, print_table

app = typer.Typer(help="Manage snippets")

_REPO_OPT = Annotated[str, typer.Option("--repo", "-R", help="workspace/slug")]


def _fmt_snip_row(s: dict) -> list[str]:
    owner = (s.get("owner") or {}).get("display_name", "")
    return [
        s.get("id", ""),
        s.get("title", ""),
        owner,
        str(s.get("is_private", "")),
    ]


def _snip_path(workspace: str, snip_id: str) -> str:
    return f"/snippets/{workspace}/{snip_id}"


@app.command("list")
def snippet_list(
    role: str = typer.Option("owner", "--role", help="owner|contributor|member"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List snippets."""
    client = make_client()
    items = list(client.paginate("/snippets", role=role))
    if as_json:
        print_json(items)
        return
    print_table(["ID", "TITLE", "OWNER", "PRIVATE"], [_fmt_snip_row(s) for s in items])


@app.command("view")
def snippet_view(
    workspace: str = typer.Argument(..., help="Workspace slug"),
    snip_id: str = typer.Argument(..., help="Snippet ID"),
    raw: bool = typer.Option(False, "--raw", help="Print raw file content"),
    file: Optional[str] = typer.Option(None, "--file", help="File name (use with --raw)"),
) -> None:
    """View a snippet."""
    if raw:
        if not file:
            raise BBError("--file is required with --raw")
        path = f"{_snip_path(workspace, snip_id)}/files/{file}"
        typer.echo(raw_request("GET", path))
        return
    client = make_client()
    s = client.get(_snip_path(workspace, snip_id))
    typer.echo(f"Title:   {s.get('title', '')}")
    typer.echo(f"Owner:   {(s.get('owner') or {}).get('display_name', '')}")
    typer.echo(f"Private: {s.get('is_private', '')}")
    typer.echo(f"Files:   {', '.join((s.get('files') or {}).keys())}")


@app.command("create")
def snippet_create(
    title: str = typer.Option(..., "--title", help="Snippet title"),
    file: str = typer.Option(..., "--file", help="Path to file to upload"),
    private: bool = typer.Option(True, "--private/--public", help="Visibility"),
) -> None:
    """Create a snippet."""
    fpath = Path(file)
    if not fpath.exists():
        raise BBError(f"file not found: {file!r}")
    content = fpath.read_bytes()
    data = {"title": title, "is_private": str(private).lower()}
    result = post_files("/snippets", data=data, files={"file": (fpath.name, content)})
    typer.echo(result.get("id", ""))


@app.command("edit")
def snippet_edit(
    workspace: str = typer.Argument(..., help="Workspace slug"),
    snip_id: str = typer.Argument(..., help="Snippet ID"),
    title: Optional[str] = typer.Option(None, "--title", help="New title"),
) -> None:
    """Edit a snippet (title only)."""
    if title is None:
        raise BBError("provide --title")
    client = make_client()
    client.put(_snip_path(workspace, snip_id), json_body={"title": title})


@app.command("delete")
def snippet_delete(
    workspace: str = typer.Argument(..., help="Workspace slug"),
    snip_id: str = typer.Argument(..., help="Snippet ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a snippet."""
    if not yes:
        typer.confirm(f"Delete snippet {snip_id}?", abort=True)
    client = make_client()
    client.delete(_snip_path(workspace, snip_id))
