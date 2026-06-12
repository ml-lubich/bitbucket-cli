"""
pipeline.py — Bitbucket Pipelines commands.

Inputs:  --repo workspace/slug override, pipeline uuid or branch name.
Outputs: table for list/steps; detail text for view; logs to stdout.
Failure: ApiError on non-2xx; BBError on missing args; ContextError without git.

NOTE: Bitbucket pipelines collection endpoint requires a trailing slash.
"""
from __future__ import annotations

from typing import Annotated, Optional

import typer

from bb.core.client import ApiClient, make_client, raw_request
from bb.core.context import RepoContext, current_repo, current_branch
from bb.core.errors import BBError
from bb.core.out import print_json, print_table

app = typer.Typer(help="Manage pipelines")

_REPO_OPT = Annotated[str, typer.Option("--repo", "-R", help="workspace/slug")]


def _pipelines_base(repo: RepoContext) -> str:
    return f"/repositories/{repo.workspace}/{repo.slug}/pipelines/"


def _pipeline_path(repo: RepoContext, uuid: str) -> str:
    return f"/repositories/{repo.workspace}/{repo.slug}/pipelines/{uuid}"


def _norm_uuid(uuid: str) -> str:
    if uuid.startswith("{") and uuid.endswith("}"):
        return uuid
    return "{" + uuid + "}"


def _fmt_status(pipeline: dict) -> str:
    state = pipeline.get("state") or {}
    name = state.get("name", "")
    result = (state.get("result") or {}).get("name", "")
    return f"{name}/{result}" if result else name


def _fmt_pipe_row(p: dict) -> list[str]:
    target = p.get("target") or {}
    branch = target.get("ref_name") or target.get("ref_type", "")
    return [
        str(p.get("build_number", "")),
        _fmt_status(p),
        branch,
        str(p.get("created_on", ""))[:10],
        str(p.get("uuid", "")),
    ]


def _fmt_step_row(step: dict) -> list[str]:
    state = step.get("state") or {}
    return [step.get("name", ""), state.get("name", ""), str(step.get("uuid", ""))]


def _emit_step_log(repo: RepoContext, pipe_uuid: str, step_uuid: str, name: str) -> None:
    typer.echo(f"== step: {name} ==")
    path = (
        f"/repositories/{repo.workspace}/{repo.slug}"
        f"/pipelines/{pipe_uuid}/steps/{step_uuid}/log"
    )
    typer.echo(raw_request("GET", path))


@app.command("list")
def pipeline_list(
    repo: _REPO_OPT = "",
    limit: int = typer.Option(20, help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List recent pipelines."""
    client = make_client()
    ctx = current_repo(repo)
    items = list(
        client.paginate(_pipelines_base(ctx), sort="-created_on", pagelen=str(limit))
    )[:limit]
    if as_json:
        print_json(items)
        return
    print_table(["BUILD", "STATUS", "BRANCH", "CREATED", "UUID"], [_fmt_pipe_row(p) for p in items])


@app.command("run")
def pipeline_run(
    repo: _REPO_OPT = "",
    branch: Optional[str] = typer.Option(None, "--branch", help="Branch to run"),
) -> None:
    """Trigger a pipeline run."""
    ref_name = branch or current_branch()
    client = make_client()
    ctx = current_repo(repo)
    payload = {"target": {"ref_type": "branch", "type": "pipeline_ref_target", "ref_name": ref_name}}
    result = client.post(_pipelines_base(ctx), json_body=payload)
    typer.echo(f"{result.get('build_number', '')} {result.get('uuid', '')}")


@app.command("view")
def pipeline_view(
    uuid: str = typer.Argument(..., help="Pipeline UUID"),
    repo: _REPO_OPT = "",
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """View pipeline details."""
    client = make_client()
    ctx = current_repo(repo)
    norm = _norm_uuid(uuid)
    p = client.get(_pipeline_path(ctx, norm))
    if as_json:
        print_json(p)
        return
    target = p.get("target") or {}
    creator = (p.get("creator") or {}).get("display_name", "")
    typer.echo(f"Build:    {p.get('build_number', '')}")
    typer.echo(f"State:    {_fmt_status(p)}")
    typer.echo(f"Branch:   {target.get('ref_name', target.get('ref_type', ''))}")
    typer.echo(f"Creator:  {creator}")
    typer.echo(f"Created:  {p.get('created_on', '')}")
    typer.echo(f"Duration: {p.get('duration_in_seconds', '')}s")


@app.command("steps")
def pipeline_steps(
    uuid: str = typer.Argument(..., help="Pipeline UUID"),
    repo: _REPO_OPT = "",
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List pipeline steps."""
    client = make_client()
    ctx = current_repo(repo)
    norm = _norm_uuid(uuid)
    items = list(client.paginate(f"{_pipeline_path(ctx, norm)}/steps/"))
    if as_json:
        print_json(items)
        return
    print_table(["NAME", "STATE", "UUID"], [_fmt_step_row(s) for s in items])


@app.command("logs")
def pipeline_logs(
    uuid: str = typer.Argument(..., help="Pipeline UUID"),
    repo: _REPO_OPT = "",
    step: Optional[str] = typer.Option(None, "--step", help="Step UUID (omit for all steps)"),
) -> None:
    """Print pipeline step logs."""
    client = make_client()
    ctx = current_repo(repo)
    norm = _norm_uuid(uuid)
    if step:
        _emit_step_log(ctx, norm, step, step)
        return
    steps = list(client.paginate(f"{_pipeline_path(ctx, norm)}/steps/"))
    for s in steps:
        _emit_step_log(ctx, norm, str(s.get("uuid", "")), s.get("name", ""))


@app.command("stop")
def pipeline_stop(
    uuid: str = typer.Argument(..., help="Pipeline UUID"),
    repo: _REPO_OPT = "",
) -> None:
    """Stop a running pipeline."""
    client = make_client()
    ctx = current_repo(repo)
    norm = _norm_uuid(uuid)
    client.post(f"{_pipeline_path(ctx, norm)}/stopPipeline")
