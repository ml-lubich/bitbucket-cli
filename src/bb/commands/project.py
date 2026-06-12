"""
project.py — Project management commands.
Inputs: workspace flag (fallback to git remote), key/name args.
Outputs: tables/JSON on stdout.
Failure: BBError when workspace cannot be resolved.
"""
from __future__ import annotations

from typing import Any, Optional

import typer

from bb.core.client import make_client
from bb.core.context import resolve_repo
from bb.core.out import print_json, print_table

app = typer.Typer(help="Manage projects", no_args_is_help=True)

_LIST_COLS = ["KEY", "NAME", "DESCRIPTION", "PRIVATE"]


def _resolve_ws(workspace: Optional[str]) -> str:
    if workspace:
        return workspace
    ctx = resolve_repo()
    return ctx.workspace


def _fmt_proj_row(p: dict[str, Any]) -> list[str]:
    desc = str(p.get("description") or "")
    return [
        str(p.get("key", "")),
        str(p.get("name", "")),
        desc[:40],
        str(p.get("is_private", False)),
    ]


def _fmt_proj_view(p: dict[str, Any]) -> None:
    link = ((p.get("links") or {}).get("html") or {}).get("href", "")
    typer.echo(f"key:        {p.get('key', '')}")
    typer.echo(f"name:       {p.get('name', '')}")
    typer.echo(f"desc:       {p.get('description', '')}")
    typer.echo(f"private:    {p.get('is_private', False)}")
    typer.echo(f"created_on: {p.get('created_on', '')}")
    typer.echo(f"url:        {link}")


@app.command("list")
def proj_list(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List projects in a workspace."""
    ws = _resolve_ws(workspace)
    client = make_client()
    items = list(client.paginate(f"/workspaces/{ws}/projects"))
    if as_json:
        print_json(items)
        return
    print_table(_LIST_COLS, [_fmt_proj_row(p) for p in items])


@app.command("view")
def proj_view(
    key: str = typer.Argument(..., help="Project key"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Show details for a project."""
    ws = _resolve_ws(workspace)
    client = make_client()
    p = client.get(f"/workspaces/{ws}/projects/{key}")
    _fmt_proj_view(p)


@app.command("create")
def proj_create(
    key: str = typer.Option(..., "--key"),
    name: str = typer.Option(..., "--name"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    private: bool = typer.Option(True, "--private/--public"),
    description: str = typer.Option("", "--description"),
) -> None:
    """Create a new project."""
    ws = _resolve_ws(workspace)
    body: dict[str, Any] = {
        "key": key,
        "name": name,
        "is_private": private,
        "description": description,
    }
    client = make_client()
    p = client.post(f"/workspaces/{ws}/projects", json_body=body)
    typer.echo(f"created project {p.get('key', '')} in {ws}")
