"""
api.py — Raw Bitbucket API calls.
Inputs: endpoint path, HTTP method, optional key=value fields.
Outputs: JSON to stdout via rich.
Failure: APIError propagates as non-zero exit.
"""
from __future__ import annotations

from typing import Optional

import typer

from bb.core.auth import AuthError, resolve_credential
from bb.core.client import APIError, BBClient
from bb.core.errors import BBError
from bb.core.out import print_json

app = typer.Typer(help="Make raw API calls", no_args_is_help=True)


def _parse_fields(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise BBError(f"invalid -f value {pair!r}; expected key=value")
        key, _, val = pair.partition("=")
        result[key.strip()] = val.strip()
    return result


def _make_client() -> BBClient:
    return BBClient(resolve_credential())


@app.command("request")
def request_cmd(
    endpoint: str = typer.Argument(..., help="API path, e.g. /repositories/myws"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    field: Optional[list[str]] = typer.Option(None, "--field", "-f", help="key=value fields"),
    paginate: bool = typer.Option(False, "--paginate", help="Follow pagination"),
) -> None:
    """Make a raw API request and print JSON."""
    client = _make_client()
    fields = _parse_fields(field or [])
    if paginate:
        items = list(client.paginate(endpoint, **fields))
        print_json(items)
        return
    data = _dispatch(client, method.upper(), endpoint, fields)
    print_json(data)


def _dispatch(
    client: BBClient,
    method: str,
    path: str,
    fields: dict[str, str],
) -> object:
    _MAP = {
        "GET": lambda: client.get(path, **fields),
        "POST": lambda: client.post(path, json=fields or None),
        "PUT": lambda: client.put(path, json=fields or None),
        "DELETE": lambda: client.delete(path) or {},
    }
    handler = _MAP.get(method)
    if handler is None:
        typer.echo(f"error: unsupported method {method!r}", err=True)
        raise typer.Exit(1)
    return handler()
