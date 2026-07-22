"""
cli.py — Root typer app; wires command groups via dict dispatch.

Inputs : argv.
Outputs: command output on stdout; errors as `bb: <message>` on stderr.
Failure: BBError subclasses exit with their exit_code (default 1).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Optional, cast

import typer
from typer._click.core import Command, Context
from typer._click.exceptions import ClickException

from bb import __version__
from bb.commands import (
    api,
    auth,
    branch,
    browse,
    config_cmd,
    doctor,
    issue,
    mcp,
    pipeline,
    pr,
    project,
    repo,
    search,
    snippet,
    workspace,
)
from bb.commands import (
    status as status_cmd,
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
    "search": search.app,
    "mcp": mcp.app,
}
_HELP_OPTIONS: dict[str, object] = {"help_option_names": ["-h", "--help"]}
_HELP_COMMAND_CONTEXT: dict[str, object] = _HELP_OPTIONS | {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
}

app = typer.Typer(
    no_args_is_help=True,
    help="bb — Bitbucket Cloud CLI",
    context_settings=_HELP_OPTIONS,
)

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


@app.command("help", context_settings=_HELP_COMMAND_CONTEXT)
def help_cmd(ctx: typer.Context) -> None:
    """Show help for bb or a nested command."""
    root_ctx = _get_root_ctx(ctx)
    command, help_ctx = _find_help_target(root_ctx, list(ctx.args))
    typer.echo(command.get_help(help_ctx))


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


def _get_root_ctx(ctx: typer.Context) -> Context:
    if ctx.parent is None:
        raise ClickException("help context is missing a parent command")
    return ctx.parent


def _find_help_target(
    root_ctx: Context,
    args: list[str],
) -> tuple[Command, Context]:
    command = root_ctx.command
    help_ctx = root_ctx
    for arg in args:
        command = _get_subcommand(command, arg)
        help_ctx = Context(command, info_name=arg, parent=help_ctx)
    return command, help_ctx


def _get_subcommand(command: Command, arg: str) -> Command:
    commands = _get_commands(command, arg)
    subcommand = commands.get(arg)
    if subcommand is None:
        raise ClickException(f"unknown command {arg!r}")
    return subcommand


def _get_commands(command: Command, arg: str) -> Mapping[str, Command]:
    commands = getattr(command, "commands", {})
    if not isinstance(commands, dict):
        raise ClickException(f"{arg!r} is not a command group")
    return cast(Mapping[str, Command], commands)


def _merge_help_context(settings: object) -> dict[str, object]:
    if isinstance(settings, dict):
        return settings | _HELP_OPTIONS
    return _HELP_OPTIONS.copy()


def _apply_help_options(typer_app: typer.Typer) -> None:
    typer_app.info.context_settings = _merge_help_context(typer_app.info.context_settings)
    for command in typer_app.registered_commands:
        command.context_settings = _merge_help_context(command.context_settings)
    for group in typer_app.registered_groups:
        group.context_settings = _merge_help_context(group.context_settings)
        if group.typer_instance is not None:
            _apply_help_options(group.typer_instance)


def _register_groups() -> None:
    for name, sub in _GROUPS.items():
        app.add_typer(sub, name=name)
    app.command("browse")(browse.browse)
    app.command("api")(api.api_cmd)
    app.command("doctor")(doctor.doctor)
    app.command("status")(status_cmd.status)
    _apply_help_options(app)


_register_groups()


def main() -> None:
    try:
        app()
    except BBError as exc:
        typer.echo(f"bb: {exc.message}", err=True)
        raise SystemExit(exc.exit_code)
