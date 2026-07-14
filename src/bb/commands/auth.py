"""
auth.py — Authenticate with Bitbucket.

Inputs: --token / --with-token, or secure prompt; optional username for basic auth.
Outputs: OS keyring (preferred) or hosts.toml credential store (mode 0600).
Failure: non-zero exit when verify call fails.
"""
from __future__ import annotations

import sys
import time

import typer

from bb.core.auth import (
    Credential,
    delete_credential,
    git_https_config_args,
    maybe_refresh,
    refresh_credential,
    resolve_credential,
    save_credential,
)
from bb.core.client import ApiClient
from bb.core.config import load_settings, set_user_value
from bb.core.deployment import Deployment, deployment_from_base_url
from bb.core.errors import ApiError, AuthError, BBError
from bb.core.validation import validate_auth_type

app = typer.Typer(
    help="Authenticate with Bitbucket (token stored in OS keyring).",
    no_args_is_help=True,
)


def _verify_user(cred: Credential, deployment: Deployment | None = None) -> str:
    """Verify credentials and return a display name when the API exposes one."""
    client = ApiClient(cred, deployment=deployment)
    if client.deployment.is_datacenter:
        client.get("/projects", limit=1)
        return cred.username or "authenticated"
    data = client.get("/user")
    return str(data.get("display_name") or data.get("username") or "unknown")


def _mask(token: str) -> str:
    """Mask token: show first 4 chars then ****."""
    return token[:4] + "****" if len(token) > 4 else "****"


def _show_user_status(cred: Credential, deployment: Deployment | None = None) -> None:
    """Print display_name from GET /user; token present but rejected → exit 1."""
    try:
        name = _verify_user(cred, deployment)
        typer.echo(f"user:   {name}")
    except (ApiError, AuthError) as exc:
        typer.echo(f"error: token present but rejected: {exc}", err=True)
        raise typer.Exit(1)


def _call_verify_user(cred: Credential, deployment: Deployment) -> str:
    try:
        return _verify_user(cred, deployment)
    except TypeError as exc:
        try:
            return _verify_user(cred)
        except TypeError:
            raise exc from None


def _call_show_user_status(cred: Credential, deployment: Deployment) -> None:
    try:
        _show_user_status(cred, deployment)
    except TypeError as exc:
        try:
            _show_user_status(cred)
        except TypeError:
            raise exc from None


def _read_token_stdin() -> str:
    if sys.stdin.isatty():
        raise AuthError("no token on stdin; pipe a token or pass --token")
    return sys.stdin.read().strip()


def _resolve_login_token(*, token: str, with_token: bool) -> str:
    if token and with_token:
        raise AuthError("use only one of --token or --with-token")
    if with_token:
        value = _read_token_stdin()
    elif token:
        value = token
    else:
        value = typer.prompt("Paste your Bitbucket token", hide_input=True)
    if not value:
        raise AuthError("token cannot be empty")
    return value


def _persist_login(
    cred: Credential,
    deployment: Deployment,
    *,
    base_url: str,
    no_verify: bool,
) -> None:
    if no_verify:
        save_credential(cred)
        if base_url:
            set_user_value("base_url", deployment.web_url)
        typer.echo("token saved")
        return
    try:
        name = _call_verify_user(cred, deployment)
    except (ApiError, AuthError) as exc:
        typer.echo(f"error: token rejected: {exc}", err=True)
        raise typer.Exit(1) from exc
    save_credential(cred)
    if base_url:
        set_user_value("base_url", deployment.web_url)
    typer.echo(f"logged in as {name}")


def _oauth_login(deployment: Deployment, *, base_url: str, no_verify: bool) -> None:
    """Cloud + TTY + no token flags: browser OAuth 2.0 authorization-code flow."""
    from bb.core import oauth

    try:
        client = oauth.resolve_oauth_client()
    except AuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    def _print_url(url: str) -> None:
        typer.echo("Opening your browser to authorize bb...")
        typer.echo(f"If it does not open automatically, visit:\n  {url}")

    try:
        token_resp = oauth.run_loopback_login(client, print_url=_print_url)
    except AuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    cred = Credential(
        token=token_resp.access_token,
        host=deployment.host,
        auth_type="oauth",
        refresh_token=token_resp.refresh_token,
        expires_at=time.time() + token_resp.expires_in,
    )
    _persist_login(cred, deployment, base_url=base_url, no_verify=no_verify)


@app.command()
def login(
    token: str = typer.Option(
        "",
        "--token",
        help="Access token (prefer env BB_TOKEN in scripts).",
        show_default=False,
    ),
    with_token: bool = typer.Option(
        False,
        "--with-token",
        help="Read token from stdin (non-interactive).",
    ),
    username: str = typer.Option(
        "",
        "--username",
        help="Account email/username for basic auth (ATATT tokens).",
        show_default=False,
    ),
    base_url: str = typer.Option(
        "",
        "--base-url",
        help="Bitbucket base URL (Cloud or Data Center).",
        show_default=False,
    ),
    auth_type: str = typer.Option(
        "",
        "--auth-type",
        help="Auth type: bearer (default) or basic.",
        show_default=False,
    ),
    no_verify: bool = typer.Option(
        False,
        "--no-verify",
        help="Skip API verification after storing the token.",
    ),
) -> None:
    """Log in to Bitbucket.

    On Bitbucket Cloud with no token flags and an interactive terminal, this
    opens your browser for OAuth login (token stored in the OS keyring, with
    automatic refresh). Data Center always requires a token — pass
    --with-token or --token. Paste a token once; it is stored in the OS
    keyring (macOS Keychain / Linux Secret Service) and reused until
    `bb auth logout`. Falls back to a mode-0600 hosts.toml file when no
    keyring is available.
    """
    deployment = deployment_from_base_url(base_url or load_settings().base_url)
    has_token_flags = bool(token) or with_token

    if not has_token_flags and deployment.is_datacenter:
        typer.echo("Data Center requires a token. Run: bb auth login --with-token", err=True)
        if not sys.stdin.isatty():
            raise typer.Exit(1)
        # Fall through to the interactive token prompt below (never SSO).

    if not has_token_flags and deployment.is_cloud:
        if not sys.stdin.isatty():
            typer.echo(
                "error: not a terminal — pass --with-token, --token, or set BB_TOKEN",
                err=True,
            )
            raise typer.Exit(1)
        _oauth_login(deployment, base_url=base_url, no_verify=no_verify)
        return

    try:
        value = _resolve_login_token(token=token, with_token=with_token)
        resolved_auth_type = auth_type or ("basic" if username and deployment.is_cloud else "bearer")
        resolved_auth_type = validate_auth_type(resolved_auth_type)
        if auth_type == "oauth":
            raise AuthError(
                'auth type "oauth" is set via browser login '
                "(`bb auth login` with no token flags), not --auth-type"
            )
    except BBError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if resolved_auth_type == "basic" and not username:
        typer.echo("error: --username is required for basic auth", err=True)
        raise typer.Exit(1)
    cred = Credential(
        token=value,
        host=deployment.host,
        auth_type=resolved_auth_type,
        username=username if resolved_auth_type == "basic" else "",
    )
    _persist_login(cred, deployment, base_url=base_url, no_verify=no_verify)


@app.command()
def logout() -> None:
    """Remove stored Bitbucket credentials from keyring and local config."""
    deployment = deployment_from_base_url(load_settings().base_url)
    removed = delete_credential(deployment.host)
    msg = "logged out" if removed else "no credentials stored"
    typer.echo(msg)


@app.command()
def status() -> None:
    """Show credential source and verify against the API."""
    deployment = deployment_from_base_url(load_settings().base_url)
    try:
        cred = resolve_credential(host=deployment.host)
    except AuthError:
        typer.echo("not authenticated — run `bb auth login`", err=True)
        raise typer.Exit(1)
    try:
        cred = maybe_refresh(cred)
    except AuthError:
        typer.echo("warning: token refresh failed; showing stored credentials", err=True)
    typer.echo(f"token:  {_mask(cred.token)}")
    typer.echo(f"source: {cred.source}")
    typer.echo(f"host:   {deployment.host}")
    _call_show_user_status(cred, deployment)


@app.command("token")
def token_cmd() -> None:
    """Print the active access token (for scripting). Never share the output."""
    deployment = deployment_from_base_url(load_settings().base_url)
    try:
        cred = maybe_refresh(resolve_credential(host=deployment.host))
    except AuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(cred.token)


@app.command()
def refresh() -> None:
    """Force a token refresh for an OAuth login (Bitbucket rotates refresh tokens)."""
    deployment = deployment_from_base_url(load_settings().base_url)
    try:
        cred = resolve_credential(host=deployment.host)
    except AuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    try:
        refresh_credential(cred)
    except AuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo("token refreshed")


@app.command("setup-git")
def setup_git() -> None:
    """Print the `git -c` flags that authenticate HTTPS clone/fetch/push with the stored credential."""
    deployment = deployment_from_base_url(load_settings().base_url)
    try:
        cred = resolve_credential(host=deployment.host)
    except AuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    args = git_https_config_args(cred)
    typer.echo(" ".join(args))
