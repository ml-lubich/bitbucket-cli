"""
api.py — Raw Bitbucket API call via `bb api <endpoint>` (gh-api style).
Inputs: endpoint path, HTTP method (-X), key=value fields (-f) or --input file.
Outputs: pretty-printed JSON (or raw text) to stdout.
Failure: BBError/ApiError propagate as non-zero exit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

import bb.core.client as _client_mod
from bb.core.errors import BBError
from bb.core.validation import validate_method


def _parse_fields(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise BBError(f"invalid -f value {pair!r}; expected key=value")
        key, _, val = pair.partition("=")
        result[key.strip()] = val.strip()
    return result


def _fmt_json_or_text(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2)
    except (json.JSONDecodeError, ValueError):
        return text


def _build_body(method: str, fields: dict[str, str], input_file: Optional[Path]) -> str:
    if input_file is not None:
        return input_file.read_text(encoding="utf-8")
    # gh parity: -f pairs become the JSON body on mutating methods
    if method != "GET" and fields:
        return json.dumps(fields)
    return ""


def api_cmd(
    endpoint: str = typer.Argument(..., help="API endpoint, e.g. /user"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    base_url: str = typer.Option("", "--base-url", help="Bitbucket base URL override."),
    field: Optional[list[str]] = typer.Option(None, "--field", "-f", help="key=value fields"),
    input_file: Optional[Path] = typer.Option(None, "--input", help="JSON body from file"),
) -> None:
    """Make a raw Bitbucket API request and pretty-print the response."""
    if input_file is not None and field:
        raise BBError("--input and --field are mutually exclusive")
    verb = validate_method(method)
    fields = _parse_fields(field or [])
    body = _build_body(verb, fields, input_file)
    params = fields if verb == "GET" and fields else None
    if base_url:
        text = _client_mod.raw_request(verb, endpoint, params, body=body, base_url=base_url)
    else:
        text = _client_mod.raw_request(verb, endpoint, params, body=body)
    typer.echo(_fmt_json_or_text(text))
