"""
api.py — Raw Bitbucket API call via `bb api <endpoint>` (gh-api style).
Inputs: endpoint path, HTTP method (-X), key=value fields (-f/-F) or --input file.
Outputs: pretty-printed JSON (or raw text) to stdout.
Failure: BBError/ApiError propagate as non-zero exit.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

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


def _coerce_typed(value: str) -> Any:
    """gh -F semantics: true/false/null/int are auto-coerced; everything else stays a string."""
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _parse_typed_fields(pairs: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise BBError(f"invalid -F value {pair!r}; expected key=value")
        key, _, val = pair.partition("=")
        result[key.strip()] = _coerce_typed(val.strip())
    return result


def _fmt_json_or_text(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2)
    except (json.JSONDecodeError, ValueError):
        return text


def _build_body(
    method: str, fields: dict[str, Any], input_file: Optional[Path]
) -> str:
    if input_file is not None:
        return input_file.read_text(encoding="utf-8")
    # gh parity: -f/-F pairs become the JSON body on mutating methods
    if method != "GET" and fields:
        return json.dumps(fields)
    return ""


def _run_jq(text: str, expr: str) -> str:
    jq_bin = shutil.which("jq")
    if jq_bin is None:
        raise BBError("jq not found — install jq to use --jq", exit_code=1)
    proc = subprocess.run(
        [jq_bin, expr],
        input=text,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise BBError(proc.stderr.strip() or "jq: filter failed")
    return proc.stdout.rstrip("\n")


def _paginate(
    verb: str,
    endpoint: str,
    params: dict[str, Any] | None,
    body: str,
    base_url: str,
    limit: Optional[int],
) -> str:
    """Follow Bitbucket Cloud 2.0 `next` links, concatenating `values` arrays."""
    if limit is not None and limit < 1:
        raise BBError(f"invalid --limit {limit}; must be >= 1")
    values: list[Any] = []
    other_keys: dict[str, Any] = {}
    url: str | None = endpoint
    cur_params = params
    while url:
        kwargs: dict[str, Any] = {}
        if base_url:
            kwargs["base_url"] = base_url
        text = _client_mod.raw_request(verb, url, cur_params, body=body, **kwargs)
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Non-JSON / non-paginated response: return as-is on first page.
            if not values:
                return text
            break
        if not isinstance(data, dict) or "values" not in data:
            # Not a paginated envelope: return as-is on first page.
            if not values:
                return text
            break
        values.extend(data.get("values") or [])
        for key, val in data.items():
            if key not in ("values", "next"):
                other_keys[key] = val
        if limit is not None and len(values) >= limit:
            values = values[:limit]
            url = None
            break
        next_url = data.get("next")
        url = str(next_url) if next_url else None
        cur_params = None
    result: dict[str, Any] = dict(other_keys)
    result["values"] = values
    return json.dumps(result)


def api_cmd(
    endpoint: str = typer.Argument(..., help="API endpoint, e.g. /user"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    base_url: str = typer.Option("", "--base-url", help="Bitbucket base URL override."),
    field: Optional[list[str]] = typer.Option(
        None, "--raw-field", "-f", help="key=value string fields (added to body/query)"
    ),
    typed_field: Optional[list[str]] = typer.Option(
        None,
        "--field",
        "-F",
        help="key=value fields with type coercion (true/false/null/int)",
    ),
    input_file: Optional[Path] = typer.Option(None, "--input", help="JSON body from file"),
    paginate: bool = typer.Option(
        False, "--paginate", help="Follow `next` pagination links, concatenating `values`"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Max total items to return when --paginate is set"
    ),
    jq_expr: Optional[str] = typer.Option(
        None, "--jq", help="Filter the JSON response through a system `jq` binary"
    ),
) -> None:
    """Make a raw Bitbucket API request and pretty-print the response."""
    if input_file is not None and (field or typed_field):
        raise BBError("--input and --raw-field/--field are mutually exclusive")
    verb = validate_method(method)
    fields: dict[str, Any] = _parse_fields(field or [])
    fields.update(_parse_typed_fields(typed_field or []))
    body = _build_body(verb, fields, input_file)
    params = fields if verb == "GET" and fields else None

    if paginate:
        text = _paginate(verb, endpoint, params, body, base_url, limit)
    elif base_url:
        text = _client_mod.raw_request(verb, endpoint, params, body=body, base_url=base_url)
    else:
        text = _client_mod.raw_request(verb, endpoint, params, body=body)

    if jq_expr is not None:
        typer.echo(_run_jq(text, jq_expr))
    else:
        typer.echo(_fmt_json_or_text(text))
