"""
config_cmd.py — Manage bb user configuration.
Inputs: key, value pairs via bb.core.config.
Outputs: printed values on get; updated config.toml on set.
Failure: ConfigError on unknown keys (exit 1).
"""
from __future__ import annotations

import typer

from bb.core.config import get_value, set_value
from bb.core.errors import ConfigError

app = typer.Typer(help="Manage bb configuration", no_args_is_help=True)


@app.command("get")
def get_cmd(key: str = typer.Argument(..., help="Config key to read")) -> None:
    """Print a configuration value."""
    try:
        typer.echo(get_value(key))
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)


@app.command("set")
def set_cmd(
    key: str = typer.Argument(..., help="Config key"),
    value: str = typer.Argument(..., help="Config value"),
) -> None:
    """Write a configuration value."""
    try:
        set_value(key, value)
        typer.echo(f"{key} = {value}")
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)
