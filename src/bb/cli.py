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
    _shell = shell.lower()
    if _shell not in _SHELLS:
        typer.echo(f"error: unknown shell {shell!r}; supported: {', '.join(_SHELLS)}", err=True)
        raise typer.Exit(1)
    typer.echo(_build_completion(_shell))


def _build_completion(shell: str) -> str:
    scripts = {
        "zsh": (
            "#compdef bb\n"
            "# bb zsh completion\n"
            "# Source with: eval \"$(bb completion zsh)\"\n"
            "_BB_COMPLETE=zsh_source bb 2>/dev/null || true\n"
        ),
        "bash": (
            "# bb bash completion\n"
            "# Source with: eval \"$(bb completion bash)\"\n"
            "_BB_COMPLETE=bash_source bb 2>/dev/null || true\n"
        ),
        "fish": (
            "# bb fish completion\n"
            "_BB_COMPLETE=fish_source bb 2>/dev/null || true\n"
        ),
        "powershell": (
            "# bb PowerShell completion\n"
            "$env:_BB_COMPLETE = 'powershell_source'; bb 2>$null\n"
        ),
    }
    return scripts[shell]


def _register_groups() -> None:
    for name, sub in _GROUPS.items():
        app.add_typer(sub, name=name)
    app.command("browse")(browse.browse)


_register_groups()


def main() -> None:
    try:
        app()
    except BBError as exc:
        typer.echo(f"bb: {exc.message}", err=True)
        raise SystemExit(exc.exit_code)
