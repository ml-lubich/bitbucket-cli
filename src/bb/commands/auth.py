"""
auth.py — Authenticate with Bitbucket.
Inputs: token via stdin/prompt, optional username for basic auth.
Outputs: hosts.toml credential store.
Failure: non-zero exit; verify call warns but does not error.
"""
from __future__ import annotations

import typer

from bb.core.auth import AuthError, Credential, delete_credential, resolve_credential, save_credential
from bb.core.client import APIError, BBClient

app = typer.Typer(help="Authenticate with Bitbucket", no_args_is_help=True)


def _whoami(cred: Credential) -> str:
    client = BBClient(cred)
    data = client.get("/user")
    return str(data.get("display_name") or data.get("username") or "unknown")


def _mask(token: str) -> str:
    return "****" + token[-4:] if len(token) > 8 else "****"


@app.command()
def login(
    token: str = typer.Option("", "--token", help="Token; prompted securely if omitted."),
    username: str = typer.Option("", "--username", help="Username for basic auth (app passwords)."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip GET /user verification."),
) -> None:
    """Store a Bitbucket access token."""
    value = token or typer.prompt("Paste your Bitbucket token", hide_input=True)
    if not value:
        typer.echo("error: token cannot be empty", err=True)
        raise typer.Exit(1)
    auth_type = "basic" if username else "bearer"
    cred = Credential(token=value, auth_type=auth_type, username=username)
    path = save_credential(cred)
    typer.echo(f"token saved to {path}")
    if not no_verify:
        _emit_whoami(cred)


def _emit_whoami(cred: Credential) -> None:
    try:
        typer.echo(f"logged in as {_whoami(cred)}")
    except (APIError, AuthError) as exc:
        typer.echo(f"warning: could not verify token: {exc}", err=True)


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
    _emit_whoami(cred)
