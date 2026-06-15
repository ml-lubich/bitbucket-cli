"""
repo.py — Repository management commands.
Inputs: workspace/slug args, --workspace flag, current git remote.
Outputs: tables/JSON on stdout; confirmation prompts on destructive ops.
Failure: BBError/ContextError propagate to cli.py error handler.
"""
from __future__ import annotations

import subprocess
from typing import Any, Optional

import typer
import tomlkit

from bb.core.client import make_client
from bb.core.config import load_settings
from bb.core.context import RepoContext, resolve_repo
from bb.core.errors import BBError
from bb.core.output import print_json, print_table

app = typer.Typer(help="Manage repositories", no_args_is_help=True)

_COLUMNS = ["NAME", "DESCRIPTION", "PRIVATE", "UPDATED"]


def _resolve_ws(workspace: Optional[str]) -> str:
    if workspace:
        return workspace
    ctx = resolve_repo()
    return ctx.workspace


def _resolve_ctx(repo_arg: Optional[str]) -> RepoContext:
    if repo_arg:
        parts = repo_arg.split("/", 1)
        if len(parts) != 2:
            raise BBError(f"invalid repo format {repo_arg!r}; expected workspace/slug")
        return RepoContext(workspace=parts[0], slug=parts[1])
    return resolve_repo()


def _fmt_row(r: dict[str, Any]) -> list[str]:
    desc = str(r.get("description") or "")
    return [
        str(r.get("full_name", "")),
        desc[:40],
        str(r.get("is_private", False)),
        str(r.get("updated_on", ""))[:10],
    ]


def _fmt_view(r: dict[str, Any]) -> None:
    mb = (r.get("mainbranch") or {}).get("name", "")
    link = ((r.get("links") or {}).get("html") or {}).get("href", "")
    typer.echo(f"name:     {r.get('full_name', '')}")
    typer.echo(f"desc:     {r.get('description', '')}")
    typer.echo(f"branch:   {mb}")
    typer.echo(f"private:  {r.get('is_private', False)}")
    typer.echo(f"lang:     {r.get('language', '')}")
    typer.echo(f"size:     {r.get('size', 0)}")
    typer.echo(f"url:      {link}")


def _clone_url(r: dict[str, Any], protocol: str) -> str:
    for entry in (r.get("links") or {}).get("clone", []):
        if entry.get("name") == protocol:
            return str(entry["href"])
    raise BBError(f"no clone URL for protocol {protocol!r}")


def _run_subprocess(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise BBError(result.stderr.strip() or "subprocess failed")


def _git_toplevel() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return r.stdout.strip()
    import os
    return os.getcwd()


def _write_default_repo(full_name: str) -> None:
    import pathlib
    root = _git_toplevel()
    path = pathlib.Path(root) / "bb.toml"
    doc = tomlkit.parse(path.read_text("utf-8")) if path.exists() else tomlkit.document()
    doc["default_repo"] = full_name
    path.write_text(tomlkit.dumps(doc), "utf-8")
    typer.echo(f"default_repo set to {full_name} in {path}")


@app.command("list")
def repo_list(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    limit: int = typer.Option(30, "--limit"),
    role: Optional[str] = typer.Option(None, "--role"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List repositories in a workspace."""
    ws = _resolve_ws(workspace)
    client = make_client()
    params: dict[str, Any] = {"pagelen": limit}
    if role:
        params["role"] = role
    items = list(client.paginate(f"/repositories/{ws}", **params))[:limit]
    if as_json:
        print_json(items)
        return
    print_table(_COLUMNS, [_fmt_row(r) for r in items])


@app.command("view")
def repo_view(
    repo_arg: Optional[str] = typer.Argument(None, metavar="workspace/slug"),
    web: bool = typer.Option(False, "--web"),
) -> None:
    """Show details for a repository."""
    ctx = _resolve_ctx(repo_arg)
    client = make_client()
    r = client.get(f"/repositories/{ctx.workspace}/{ctx.repo}")
    link = ((r.get("links") or {}).get("html") or {}).get("href", "")
    if web:
        typer.launch(link)
        return
    _fmt_view(r)


@app.command("clone")
def repo_clone(
    repo_arg: str = typer.Argument(..., metavar="workspace/slug"),
    directory: Optional[str] = typer.Argument(None),
) -> None:
    """Clone a repository."""
    ctx = _resolve_ctx(repo_arg)
    client = make_client()
    r = client.get(f"/repositories/{ctx.workspace}/{ctx.repo}")
    protocol = load_settings().git_protocol
    url = _clone_url(r, protocol)
    cmd = ["git", "clone", url]
    if directory:
        cmd.append(directory)
    _run_subprocess(cmd)


@app.command("create")
def repo_create(
    name: str = typer.Option(..., "--name"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    private: bool = typer.Option(True, "--private/--public"),
    description: str = typer.Option("", "--description"),
    project: Optional[str] = typer.Option(None, "--project"),
) -> None:
    """Create a new repository."""
    ws = _resolve_ws(workspace)
    body: dict[str, Any] = {"scm": "git", "is_private": private, "description": description}
    if project:
        body["project"] = {"key": project}
    client = make_client()
    r = client.post(f"/repositories/{ws}/{name}", json_body=body)
    link = ((r.get("links") or {}).get("html") or {}).get("href", "")
    typer.echo(f"created {r.get('full_name', '')}")
    typer.echo(f"url:    {link}")


@app.command("fork")
def repo_fork(
    repo_arg: str = typer.Argument(..., metavar="workspace/slug"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Fork a repository."""
    ctx = _resolve_ctx(repo_arg)
    body: dict[str, Any] = {}
    if workspace:
        body["workspace"] = {"slug": workspace}
    client = make_client()
    r = client.post(f"/repositories/{ctx.workspace}/{ctx.repo}/forks", json_body=body)
    typer.echo(f"forked to {r.get('full_name', '')}")


@app.command("delete")
def repo_delete(
    repo_arg: str = typer.Argument(..., metavar="workspace/slug"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete a repository."""
    ctx = _resolve_ctx(repo_arg)
    if not yes:
        typer.confirm(f"Delete {ctx.full_name}?", abort=True)
    client = make_client()
    client.delete(f"/repositories/{ctx.workspace}/{ctx.repo}")
    typer.echo(f"deleted {ctx.full_name}")


@app.command("sync")
def repo_sync() -> None:
    """Sync fork with upstream parent (git fetch + merge)."""
    ctx = resolve_repo()
    client = make_client()
    r = client.get(f"/repositories/{ctx.workspace}/{ctx.repo}")
    parent = r.get("parent")
    if not parent:
        raise BBError("not a fork — no parent repository")
    parent_url = _clone_url(parent, "https")
    mb = (r.get("mainbranch") or {}).get("name", "main")
    _run_subprocess(["git", "fetch", parent_url, mb])
    _run_subprocess(["git", "merge", "FETCH_HEAD"])
    typer.echo("synced with upstream")


@app.command("set-default")
def repo_set_default(
    repo_arg: str = typer.Argument(..., metavar="workspace/slug"),
) -> None:
    """Write default_repo into bb.toml at git root."""
    _write_default_repo(repo_arg)
