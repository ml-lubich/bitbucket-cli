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
from bb.core.context import RepoContext, current_branch, current_repo
from bb.core.output import print_json, print_table
from bb.core.validation import validate_limit

app = typer.Typer(help="Manage pipelines")
variable_app = typer.Typer(help="Manage pipeline variables")
app.add_typer(variable_app, name="variable")

_REPO_OPT = Annotated[str, typer.Option("--repo", "-R", help="workspace/slug")]


def _pipelines_base(repo: RepoContext) -> str:
    return f"/repositories/{repo.workspace}/{repo.slug}/pipelines/"


def _variables_base(repo: RepoContext) -> str:
    return f"/repositories/{repo.workspace}/{repo.slug}/pipelines_config/variables/"


def _variable_path(repo: RepoContext, uuid: str) -> str:
    return f"{_variables_base(repo)}{uuid}"


def _fmt_variable_row(v: dict) -> list[str]:
    secured = bool(v.get("secured"))
    value = "********" if secured else str(v.get("value", ""))
    return [str(v.get("uuid", "")), str(v.get("key", "")), value, str(secured)]


def _mask_variable(v: dict) -> dict:
    if not v.get("secured"):
        return v
    masked = dict(v)
    masked["value"] = "********"
    return masked


def _make_client_for_ctx(ctx: RepoContext) -> ApiClient:
    return make_client(base_url=ctx.base_url) if ctx.base_url else make_client()


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
    if repo.base_url:
        typer.echo(raw_request("GET", path, base_url=repo.base_url))
    else:
        typer.echo(raw_request("GET", path))


@app.command("list")
def pipeline_list(
    repo: _REPO_OPT = "",
    limit: int = typer.Option(20, help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List recent pipelines."""
    limit = validate_limit(limit)
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
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
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
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
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
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
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
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
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
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
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
    norm = _norm_uuid(uuid)
    client.post(f"{_pipeline_path(ctx, norm)}/stopPipeline")


@variable_app.command("list")
def variable_list(
    repo: _REPO_OPT = "",
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List pipeline variables."""
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
    items = list(client.paginate(_variables_base(ctx)))
    if as_json:
        print_json([_mask_variable(v) for v in items])
        return
    print_table(["UUID", "KEY", "VALUE", "SECURED"], [_fmt_variable_row(v) for v in items])


@variable_app.command("create")
def variable_create(
    key: str = typer.Option(..., "--key", help="Variable name"),
    value: str = typer.Option(..., "--value", help="Variable value"),
    secured: bool = typer.Option(False, "--secured", help="Mark variable as secured"),
    repo: _REPO_OPT = "",
) -> None:
    """Create a pipeline variable."""
    ctx = current_repo(repo)
    client = _make_client_for_ctx(ctx)
    payload = {"key": key, "value": value, "secured": secured}
    result = client.post(_variables_base(ctx), json_body=payload)
    shown_value = "********" if secured else result.get("value", value)
    typer.echo(f"created {result.get('key', key)} ({result.get('uuid', '')}) = {shown_value}")


@variable_app.command("delete")
def variable_delete(
    uuid: str = typer.Argument(..., help="Variable UUID"),
    repo: _REPO_OPT = "",
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a pipeline variable."""
    ctx = current_repo(repo)
    norm = _norm_uuid(uuid)
    if not yes:
        typer.confirm(f"Delete variable {norm}?", abort=True)
    client = _make_client_for_ctx(ctx)
    client.delete(_variable_path(ctx, norm))
    typer.echo(f"deleted {norm}")
