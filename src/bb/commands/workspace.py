"""
workspace.py — Workspace management commands.
Inputs: slug args.
Outputs: tables/JSON on stdout.
Failure: ApiError propagates to cli.py error handler.
"""
from __future__ import annotations

from typing import Any

import typer

from bb.core.client import make_client
from bb.core.output import print_json, print_table

app = typer.Typer(help="Manage workspaces", no_args_is_help=True)

_LIST_COLS = ["SLUG", "NAME"]
_MEMBER_COLS = ["NAME", "NICKNAME", "UUID"]


def _fmt_ws_row(ws: dict[str, Any]) -> list[str]:
    return [str(ws.get("slug", "")), str(ws.get("name", ""))]


def _fmt_member_row(m: dict[str, Any]) -> list[str]:
    user = m.get("user") or {}
    return [
        str(user.get("display_name", "")),
        str(user.get("nickname", "")),
        str(user.get("uuid", "")),
    ]


@app.command("list")
def ws_list(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List all workspaces the authenticated user belongs to."""
    client = make_client()
    items = list(client.paginate("/workspaces"))
    if as_json:
        print_json(items)
        return
    print_table(_LIST_COLS, [_fmt_ws_row(w) for w in items])


@app.command("view")
def ws_view(
    slug: str = typer.Argument(..., help="Workspace slug"),
) -> None:
    """Show details for a workspace."""
    client = make_client()
    w = client.get(f"/workspaces/{slug}")
    link = ((w.get("links") or {}).get("html") or {}).get("href", "")
    typer.echo(f"slug:       {w.get('slug', '')}")
    typer.echo(f"name:       {w.get('name', '')}")
    typer.echo(f"uuid:       {w.get('uuid', '')}")
    typer.echo(f"created_on: {w.get('created_on', '')}")
    typer.echo(f"url:        {link}")


@app.command("members")
def ws_members(
    slug: str = typer.Argument(..., help="Workspace slug"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List members of a workspace."""
    client = make_client()
    items = list(client.paginate(f"/workspaces/{slug}/members"))
    if as_json:
        print_json(items)
        return
    print_table(_MEMBER_COLS, [_fmt_member_row(m) for m in items])
