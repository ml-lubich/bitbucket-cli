"""
doctor.py — Agent-friendly environment and auth diagnostics.

Inputs: --json, --no-network.
Outputs: deterministic status report without raw secrets.
Failure: exit 1 when required checks fail.
"""
from __future__ import annotations

import typer
from pydantic import BaseModel, ConfigDict

from bb.core.auth import Credential, resolve_credential
from bb.core.client import ApiClient
from bb.core.config import load_settings
from bb.core.deployment import Deployment, deployment_from_base_url
from bb.core.errors import ApiError, AuthError
from bb.core.output import print_json, print_table


class DoctorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    provider: str
    base_url: str
    api_url: str
    host: str
    auth_source: str
    auth_ok: bool
    network_checked: bool
    errors: list[str]


def doctor(
    as_json: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
    no_network: bool = typer.Option(False, "--no-network", help="Skip live API verification."),
) -> None:
    """Check bb config, credential resolution, and optional live auth."""
    report = build_report(network=not no_network)
    if as_json:
        print_json(report.model_dump())
    else:
        _print_report(report)
    if not report.ok:
        raise typer.Exit(1)


def build_report(network: bool = True) -> DoctorReport:
    settings = load_settings()
    deployment = deployment_from_base_url(settings.base_url)
    errors: list[str] = []
    auth_source = "none"
    auth_ok = False
    try:
        cred = resolve_credential(host=deployment.host)
        auth_source = cred.source
        if network:
            _verify(deployment, cred)
        auth_ok = True
    except (AuthError, ApiError) as exc:
        errors.append(str(exc))
    return DoctorReport(
        ok=not errors,
        provider=deployment.kind,
        base_url=deployment.web_url,
        api_url=deployment.api_url,
        host=deployment.host,
        auth_source=auth_source,
        auth_ok=auth_ok,
        network_checked=network,
        errors=errors,
    )


def _verify(deployment: Deployment, cred: Credential) -> None:
    client = ApiClient(cred, deployment=deployment)
    if deployment.is_datacenter:
        client.get("/projects", limit=1)
        return
    client.get("/user")


def _print_report(report: DoctorReport) -> None:
    rows = [
        ("provider", report.provider),
        ("base_url", report.base_url),
        ("api_url", report.api_url),
        ("host", report.host),
        ("auth_source", report.auth_source),
        ("auth_ok", str(report.auth_ok)),
        ("network_checked", str(report.network_checked)),
    ]
    print_table(["CHECK", "VALUE"], rows)
    for error in report.errors:
        typer.echo(f"error: {error}", err=True)
