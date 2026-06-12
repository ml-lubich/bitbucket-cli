"""
branch.py — Branch management commands for Bitbucket Cloud.
Inputs: Credential (via resolve_credential), RepoContext (via current_repo or --repo).
Outputs: tables or confirmation prompts to stdout.
Failure modes: ApiError, ContextError, BBError.
"""
from __future__ import annotations

import typer

from bb.core.auth import resolve_credential
from bb.core.client import ApiClient
from bb.core.context import RepoContext, current_repo
from bb.core.output import print_json, print_table

app = typer.Typer(help="Manage branches")


def make_client(repo: str = "") -> tuple[ApiClient, RepoContext]:
    cred = resolve_credential()
    ctx = current_repo(override=repo)
    return ApiClient(cred), ctx


def _refs_base(ctx: RepoContext) -> str:
    return f"/repositories/{ctx.workspace}/{ctx.repo}/refs/branches"


@app.command("list")
def branch_list(
    repo: str = typer.Option("", "--repo", "-R"),
    limit: int = typer.Option(30, "--limit"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List branches."""
    client, ctx = make_client(repo)
    items = list(client.paginate(_refs_base(ctx), pagelen=limit))
    if as_json:
        print_json(items)
        return
    rows = [_branch_row(b) for b in items]
    print_table(["NAME", "TARGET", "AUTHOR"], rows)


def _branch_row(b: dict) -> tuple[str, ...]:
    name = str(b.get("name", ""))
    target = str(b.get("target", {}).get("hash", ""))[:7]
    author = str(b.get("target", {}).get("author", {}).get("user", {}).get("display_name", ""))
    return name, target, author


@app.command("create")
def branch_create(
    name: str = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    from_ref: str = typer.Option("", "--from"),
) -> None:
    """Create a branch."""
    client, ctx = make_client(repo)
    source = from_ref or _repo_mainbranch(client, ctx)
    branch_info = client.get(f"{_refs_base(ctx)}/{source}")
    hash_ = branch_info.get("target", {}).get("hash", "")
    client.post(_refs_base(ctx), json_body={"name": name, "target": {"hash": hash_}})
    typer.echo(f"Branch {name!r} created from {source} ({hash_[:7]}).")


@app.command("delete")
def branch_delete(
    name: str = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete a branch."""
    if not yes:
        typer.confirm(f"Delete branch {name!r}?", abort=True)
    client, ctx = make_client(repo)
    client.delete(f"{_refs_base(ctx)}/{name}")
    typer.echo(f"Branch {name!r} deleted.")


def _repo_mainbranch(client: ApiClient, ctx: RepoContext) -> str:
    info = client.get(f"/repositories/{ctx.workspace}/{ctx.repo}")
    return str(info.get("mainbranch", {}).get("name", "main"))
