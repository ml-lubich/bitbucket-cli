"""
api.py — Raw Bitbucket API call via `bb api request`.
Inputs: endpoint path, HTTP method, optional key=value fields.
Outputs: JSON to stdout.
Failure: ApiError propagates as non-zero exit.
"""
from __future__ import annotations

import json
from typing import Optional

import typer

import bb.core.client as _client_mod
from bb.core.errors import BBError

app = typer.Typer(help="Make raw API calls", no_args_is_help=False, invoke_without_command=True)


def _parse_fields(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise BBError(f"invalid -f value {pair!r}; expected key=value")
        key, _, val = pair.partition("=")
        result[key.strip()] = val.strip()
    return result


def _fmt_json(data: object) -> str:
    return json.dumps(data, indent=2)


@app.callback(invoke_without_command=True)
def _api_callback(
    ctx: typer.Context,
    endpoint: Optional[str] = typer.Argument(None, help="API path, e.g. /user"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    field: Optional[list[str]] = typer.Option(None, "--field", "-f", help="key=value fields"),
    paginate: bool = typer.Option(False, "--paginate", help="Follow next-page links"),
    input: Optional[str] = typer.Option(None, "--input", help="JSON body from file"),
) -> None:
    """Make a raw Bitbucket API request (shortcut for `bb api request`)."""
    if ctx.invoked_subcommand is not None or endpoint is None:
        return
    if input is not None and field:
        typer.echo("error: --input and --field are mutually exclusive", err=True)
        raise typer.Exit(1)
    fields = _parse_fields(field or []) if field else None
    text = _client_mod.raw_request(method.upper(), endpoint, fields)
    typer.echo(_fmt_json_or_text(text))


def _fmt_json_or_text(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2)
    except (json.JSONDecodeError, ValueError):
        return text


@app.command("request")
def request_cmd(
    endpoint: str = typer.Argument(..., help="API path, e.g. /user"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    field: Optional[list[str]] = typer.Option(None, "--field", "-f", help="key=value fields"),
    paginate: bool = typer.Option(False, "--paginate", help="Follow next-page links"),
) -> None:
    """Make a raw Bitbucket API request and print JSON."""
    fields = _parse_fields(field or [])
    client = _client_mod.make_client()
    if paginate:
        items = list(client.paginate(endpoint, **fields))
        typer.echo(_fmt_json(items))
        return
    data = _do_request(client, method.upper(), endpoint, fields)
    typer.echo(_fmt_json(data))


def _do_request(
    client: object,
    method: str,
    endpoint: str,
    fields: dict[str, str],
) -> object:
    dispatch = {
        "GET": lambda: client.get(endpoint, **fields),  # type: ignore[union-attr]
        "POST": lambda: client.post(endpoint, json=fields or None),  # type: ignore[union-attr]
        "PUT": lambda: client.put(endpoint, json=fields or None),  # type: ignore[union-attr]
        "DELETE": lambda: client.delete(endpoint) or {},  # type: ignore[union-attr]
    }
    handler = dispatch.get(method)
    if handler is None:
        typer.echo(f"error: unsupported method {method!r}", err=True)
        raise typer.Exit(1)
    return handler()
