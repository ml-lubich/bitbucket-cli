"""
auth.py — Authenticate with Bitbucket.
Inputs: token via --token flag or prompt, optional username for basic auth.
Outputs: hosts.toml credential store.
Failure: non-zero exit when verify call fails.
"""
from __future__ import annotations

import typer

from bb.core.auth import AuthError, Credential, delete_credential, resolve_credential, save_credential
from bb.core.client import ApiClient
from bb.core.errors import ApiError

app = typer.Typer(help="Authenticate with Bitbucket", no_args_is_help=True)


def _verify_user(cred: Credential) -> str:
    """Call GET /user and return display_name. Raises ApiError on failure."""
    client = ApiClient(cred)
    data = client.get("/user")
    return str(data.get("display_name") or data.get("username") or "unknown")


def _mask(token: str) -> str:
    """Mask token: show first 4 chars then ****."""
    return token[:4] + "****" if len(token) > 4 else "****"


def _show_user_status(cred: Credential) -> None:
    """Print display_name from GET /user; warn on failure."""
    try:
        name = _verify_user(cred)
        typer.echo(f"user:   {name}")
    except (ApiError, AuthError) as exc:
        typer.echo(f"warning: {exc}", err=True)


@app.command()
def login(
    token: str = typer.Option("", "--token", help="Token; prompted securely if omitted."),
    username: str = typer.Option("", "--username", help="Username for basic auth."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip GET /user verification."),
) -> None:
    """Store a Bitbucket access token."""
    value = token or typer.prompt("Paste your Bitbucket token", hide_input=True)
    if not value:
        typer.echo("error: token cannot be empty", err=True)
        raise typer.Exit(1)
    auth_type = "basic" if username else "bearer"
    cred = Credential(token=value, auth_type=auth_type, username=username)
    if no_verify:
        save_credential(cred)
        typer.echo("token saved")
        return
    try:
        name = _verify_user(cred)
    except (ApiError, AuthError) as exc:
        typer.echo(f"error: token rejected: {exc}", err=True)
        raise typer.Exit(1)
    save_credential(cred)
    typer.echo(f"logged in as {name}")


@app.command()
def logout() -> None:
    """Remove stored Bitbucket credentials."""
    removed = delete_credential()
    msg = "logged out" if removed else "no credentials stored"
    typer.echo(msg)


@app.command()
def status() -> None:
    """Show credential source and verify against the API."""
    try:
        cred = resolve_credential()
    except AuthError:
        typer.echo("not authenticated — run `bb auth login`", err=True)
        raise typer.Exit(1)
    typer.echo(f"token:  {_mask(cred.token)}")
    typer.echo(f"source: {cred.source}")
    _show_user_status(cred)
