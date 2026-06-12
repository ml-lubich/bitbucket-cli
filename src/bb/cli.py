"""
cli.py — Root typer app; wires command groups via dict dispatch.

Inputs : argv.
Outputs: command output on stdout; errors as `bb: <message>` on stderr.
Failure: BBError subclasses exit with their exit_code (default 1).
"""
from __future__ import annotations

from typing import Optional

import typer

from bb import __version__
from bb.commands import (
    api,
    auth,
    branch,
    browse,
    config_cmd,
    issue,
    pipeline,
    pr,
    project,
    repo,
    snippet,
    workspace,
)
from bb.core.errors import BBError

_GROUPS: dict[str, typer.Typer] = {
    "auth": auth.app,
    "pr": pr.app,
    "repo": repo.app,
    "issue": issue.app,
    "pipeline": pipeline.app,
    "branch": branch.app,
    "workspace": workspace.app,
    "project": project.app,
    "snippet": snippet.app,
    "config": config_cmd.app,
    "api": api.app,
    "browse": browse.app,
}

app = typer.Typer(no_args_is_help=True, help="bb — Bitbucket Cloud CLI")

_SHELLS = ("bash", "zsh", "fish", "powershell")


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(f"bb version {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_cb,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """bb — a lightweight gh-style CLI for Bitbucket Cloud."""


@app.command("completion")
def completion(
    shell: str = typer.Argument(..., help="Shell: bash | zsh | fish | powershell"),
) -> None:
    """Print shell completion script for the given shell."""
    from click.shell_completion import get_completion_class
    import typer.main as _tm

    cls = get_completion_class(shell.lower())
    if cls is None:
        raise BBError(f"unknown shell {shell!r}; supported: {', '.join(_SHELLS)}")
    click_cmd = _tm.get_command(app)
    comp = cls(
        cli=click_cmd,
        ctx_args={},
        prog_name="bb",
        complete_var="_BB_COMPLETE",
    )
    typer.echo(comp.source())


def _register_groups() -> None:
    for name, sub in _GROUPS.items():
        app.add_typer(sub, name=name)


_register_groups()


def main() -> None:
    try:
        app()
    except BBError as exc:
        typer.echo(f"bb: {exc.message}", err=True)
        raise SystemExit(exc.exit_code)
