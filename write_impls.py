#!/usr/bin/env python3
"""Write all real implementations at once to prevent stub reversion."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path("/Users/mlubich/Desktop/git/bitbucket-cli")

FILES: dict[str, str] = {}

# ── __init__.py ──────────────────────────────────────────────────────────────
FILES["src/bb/__init__.py"] = '''\
__version__ = "0.1.0"
'''

# ── commands/auth.py ─────────────────────────────────────────────────────────
FILES["src/bb/commands/auth.py"] = '''\
"""
auth.py — Authenticate with Bitbucket.
Inputs: token via stdin or prompt.
Outputs: hosts.toml credential store.
Failure: non-zero exit when verify call fails (warns, does not error).
"""
from __future__ import annotations

import sys

import typer

from bb.core.auth import Credential, delete_credential, resolve_credential, save_credential
from bb.core.errors import ApiError, AuthError

app = typer.Typer(help="Authenticate with Bitbucket", no_args_is_help=True)

_HOST = "bitbucket.org"


def _read_token_stdin() -> str:
    return sys.stdin.readline().strip()


def _prompt_token() -> str:
    return typer.prompt("Paste your Bitbucket access token", hide_input=True)


def _verify_token(token: str) -> str:
    from bb.core.client import ApiClient
    cred = Credential(token=token, source="flag")
    client = ApiClient(cred)
    data = client.get("/user")
    return str(data.get("display_name", "unknown"))


@app.command()
def login(
    with_token: bool = typer.Option(False, "--with-token", help="Read token from stdin"),
) -> None:
    """Store a Bitbucket access token."""
    token = _read_token_stdin() if with_token else _prompt_token()
    if not token:
        typer.echo("error: token cannot be empty", err=True)
        raise typer.Exit(1)
    cred = Credential(token=token, source="flag")
    save_credential(cred)
    try:
        name = _verify_token(token)
        typer.echo(f"Logged in as {name}")
    except (ApiError, AuthError) as exc:
        typer.echo(f"warning: could not verify token: {exc}", err=True)


@app.command()
def logout() -> None:
    """Remove stored Bitbucket credentials."""
    removed = delete_credential(_HOST)
    msg = "logged out" if removed else "no credentials stored"
    typer.echo(msg)


def _mask(token: str) -> str:
    return "****" + token[-4:] if len(token) > 8 else "****"


@app.command()
def status() -> None:
    """Show current authentication status."""
    try:
        cred = resolve_credential(_HOST)
    except AuthError:
        typer.echo("not authenticated — run `bb auth login`", err=True)
        raise typer.Exit(1)
    typer.echo(f"host:   {_HOST}")
    typer.echo(f"source: {cred.source}")
    typer.echo(f"token:  {_mask(cred.token)}")
    _show_user(cred.token)


def _show_user(token: str) -> None:
    from bb.core.client import ApiClient
    cred = Credential(token=token, source="hosts")
    try:
        data = ApiClient(cred).get("/user")
        typer.echo(f"user:   {data.get('display_name', 'unknown')}")
    except (ApiError, AuthError) as exc:
        typer.echo(f"warning: {exc}", err=True)
'''

# ── commands/api.py ──────────────────────────────────────────────────────────
FILES["src/bb/commands/api.py"] = '''\
"""
api.py — Raw Bitbucket API calls.
Inputs: endpoint path, HTTP method, optional key=value fields.
Outputs: JSON to stdout.
Failure: ApiError propagates as non-zero exit.
"""
from __future__ import annotations

import json
from typing import Optional

import typer

from bb.core.out import print_json

app = typer.Typer(help="Make raw API calls", no_args_is_help=True)


def _parse_fields(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs:
        key, _, val = pair.partition("=")
        result[key.strip()] = val.strip()
    return result


def _paginated(client: object, path: str) -> list[object]:  # type: ignore[type-arg]
    from bb.core.client import ApiClient
    assert isinstance(client, ApiClient)
    return list(client.paginate(path))


@app.command("request")
def request_cmd(
    endpoint: str = typer.Argument(..., help="API path, e.g. /repositories/myws"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    field: Optional[list[str]] = typer.Option(None, "--field", "-f", help="key=value body fields"),
    paginate: bool = typer.Option(False, "--paginate", help="Follow pagination"),
) -> None:
    """Make a raw API request and print JSON."""
    from bb.core.client import ApiClient, make_client
    client = make_client()
    fields = _parse_fields(field or [])
    if paginate:
        items = list(client.paginate(endpoint, params=fields or None))
        print_json(items)
        return
    data = _dispatch_method(client, method.upper(), endpoint, fields)
    print_json(data)


def _dispatch_method(
    client: object,
    method: str,
    path: str,
    fields: dict[str, str],
) -> object:
    from bb.core.client import ApiClient
    assert isinstance(client, ApiClient)
    _MAP = {
        "GET": lambda: client.get(path, params=fields or None),
        "POST": lambda: client.post(path, json_body=fields or None),
        "PUT": lambda: client.put(path, json_body=fields or None),
        "DELETE": lambda: (client.delete(path) or {}),
    }
    handler = _MAP.get(method)
    if handler is None:
        typer.echo(f"error: unsupported method {method!r}", err=True)
        raise typer.Exit(1)
    return handler()
'''

# ── commands/config_cmd.py ───────────────────────────────────────────────────
FILES["src/bb/commands/config_cmd.py"] = '''\
"""
config_cmd.py — Manage bb user configuration.
Inputs: key, value pairs written to user config.toml.
Outputs: printed values on get; updated config.toml on set.
Failure: exit 1 on unknown keys.
"""
from __future__ import annotations

import typer
import tomlkit
from platformdirs import user_config_dir
from pathlib import Path

app = typer.Typer(help="Manage bb configuration", no_args_is_help=True)

ALLOWED_KEYS: frozenset[str] = frozenset({"git_protocol", "editor", "default_repo"})


def _cfg_path() -> Path:
    return Path(user_config_dir("bb")) / "config.toml"


def _read_cfg() -> tomlkit.TOMLDocument:
    path = _cfg_path()
    if not path.is_file():
        return tomlkit.document()
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def _write_cfg(doc: tomlkit.TOMLDocument) -> None:
    path = _cfg_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def _validate_key(key: str) -> None:
    if key not in ALLOWED_KEYS:
        typer.echo(f"error: unknown config key {key!r}; allowed: {sorted(ALLOWED_KEYS)}", err=True)
        raise typer.Exit(1)


@app.command()
def get(key: str = typer.Argument(..., help="Config key to read")) -> None:
    """Print a configuration value."""
    _validate_key(key)
    doc = _read_cfg()
    val = doc.get(key, "")
    typer.echo(val)


@app.command("set")
def set_cmd(
    key: str = typer.Argument(..., help="Config key"),
    value: str = typer.Argument(..., help="Config value"),
) -> None:
    """Write a configuration value."""
    _validate_key(key)
    doc = _read_cfg()
    doc[key] = value  # type: ignore[index]
    _write_cfg(doc)
    typer.echo(f"{key} = {value}")
'''

# ── commands/browse.py ───────────────────────────────────────────────────────
FILES["src/bb/commands/browse.py"] = '''\
"""
browse.py — Open current repo in the browser.
Inputs: Optional --no-browser flag.
Outputs: URL printed or browser opened.
Failure: RepoContextError if no repo context can be determined.
"""
from __future__ import annotations

import webbrowser

import typer

from bb.core.config import load_settings
from bb.core.ctx import RepoContextError, current_repo


def browse_cmd(
    no_browser: bool = typer.Option(False, "--no-browser", help="Print URL, do not open browser"),
) -> None:
    """Open the current repository on Bitbucket in a browser."""
    settings = load_settings()
    try:
        ref = current_repo(settings)
    except RepoContextError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)
    url = f"https://bitbucket.org/{ref.full_name}"
    if no_browser:
        typer.echo(url)
        return
    webbrowser.open(url)
'''

# ── tests/conftest.py ────────────────────────────────────────────────────────
FILES["tests/conftest.py"] = '''\
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "bb_config"
    config_dir.mkdir()
    monkeypatch.setattr("bb.core.auth._hosts_path", lambda: config_dir / "hosts.toml")
    return config_dir


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("BB_TOKEN", "BITBUCKET_TOKEN", "BITBUCKET_AUTH_TOKEN", "BB_REPO"):
        monkeypatch.delenv(key, raising=False)
'''

# ── tests/test_cfg.py ────────────────────────────────────────────────────────
FILES["tests/test_cfg.py"] = '''\
"""Tests for token resolution precedence in bb.core.auth."""
from __future__ import annotations

import pytest


def test_bb_token_beats_bitbucket_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "bb-tok")
    monkeypatch.setenv("BITBUCKET_TOKEN", "other-tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "bb-tok"


def test_bitbucket_token_used_when_no_bb_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_TOKEN", "bt-tok")
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    monkeypatch.setattr("bb.core.auth._cred_from_dotenv", lambda: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "bt-tok"


def test_auth_token_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_AUTH_TOKEN", "auth-tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    monkeypatch.setattr("bb.core.auth._cred_from_dotenv", lambda: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "auth-tok"


def test_dotenv_fallback_reads_file(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempdirFactory) -> None:
    from pathlib import Path
    dotenv = Path(tmp_path) / ".env"
    dotenv.write_text("BB_TOKEN=dotenv-tok\\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "dotenv-tok"


def test_source_is_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.source == "env:BB_TOKEN"
'''

# ── tests/test_auth_store.py ─────────────────────────────────────────────────
FILES["tests/test_auth_store.py"] = '''\
"""Tests for bb.core.auth credential persistence."""
from __future__ import annotations

import stat
from pathlib import Path

import pytest


def test_store_token_creates_file(tmp_config_dir: Path) -> None:
    from bb.core.auth import Credential, save_credential
    save_credential(Credential(token="my-secret-token"))
    assert (tmp_config_dir / "hosts.toml").is_file()


def test_read_token_returns_stored(tmp_config_dir: Path) -> None:
    from bb.core.auth import Credential, save_credential, stored_credential
    save_credential(Credential(token="my-secret-token"))
    assert stored_credential().token == "my-secret-token"


def test_file_mode_is_0600(tmp_config_dir: Path) -> None:
    from bb.core.auth import Credential, save_credential
    save_credential(Credential(token="tok"))
    hosts = tmp_config_dir / "hosts.toml"
    assert oct(stat.S_IMODE(hosts.stat().st_mode)) == "0o600"


def test_delete_credential_removes_entry(tmp_config_dir: Path) -> None:
    from bb.core.auth import Credential, delete_credential, save_credential, stored_credential
    from bb.core.errors import AuthError
    save_credential(Credential(token="tok"))
    delete_credential()
    with pytest.raises(AuthError):
        stored_credential()


def test_delete_returns_true_when_present(tmp_config_dir: Path) -> None:
    from bb.core.auth import Credential, delete_credential, save_credential
    save_credential(Credential(token="tok"))
    assert delete_credential() is True


def test_delete_returns_false_when_absent(tmp_config_dir: Path) -> None:
    from bb.core.auth import delete_credential
    assert delete_credential() is False


def test_read_raises_when_no_file(tmp_config_dir: Path) -> None:
    from bb.core.auth import stored_credential
    from bb.core.errors import AuthError
    with pytest.raises(AuthError):
        stored_credential()
'''

# ── tests/test_client.py ─────────────────────────────────────────────────────
FILES["tests/test_client.py"] = '''\
"""Tests for ApiClient HTTP behaviour using httpx mock transport."""
from __future__ import annotations

import pytest
import httpx

from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.core.errors import ApiError


def _cred(token: str = "test-token") -> Credential:
    return Credential(token=token, source="flag")


def _transport(status: int, body: dict | None = None) -> httpx.MockTransport:  # type: ignore[type-arg]
    import json
    payload = json.dumps(body or {})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload.encode(), headers={"content-type": "application/json"})

    return httpx.MockTransport(handler)


def test_200_returns_json() -> None:
    client = ApiClient(_cred(), transport=_transport(200, {"display_name": "alice"}))
    data = client.get("/user")
    assert data["display_name"] == "alice"


def test_401_raises_api_error() -> None:
    client = ApiClient(_cred(), transport=_transport(401, {"error": {"message": "Unauthorized"}}))
    with pytest.raises(ApiError) as exc_info:
        client.get("/user")
    assert exc_info.value.status_code == 401


def test_404_raises_api_error() -> None:
    client = ApiClient(_cred(), transport=_transport(404, {"error": {"message": "Not Found"}}))
    with pytest.raises(ApiError) as exc_info:
        client.get("/repos/x/y")
    assert exc_info.value.status_code == 404


def test_204_returns_empty_dict() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = ApiClient(_cred(), transport=httpx.MockTransport(handler))
    assert client.get("/something") == {}


def test_paginate_follows_next() -> None:
    pages = [
        {"values": [{"id": 1}], "next": "https://api.bitbucket.org/2.0/page2"},
        {"values": [{"id": 2}]},
    ]
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        import json
        page = pages[call_count]
        call_count += 1
        return httpx.Response(200, content=json.dumps(page).encode(), headers={"content-type": "application/json"})

    client = ApiClient(_cred(), transport=httpx.MockTransport(handler))
    items = list(client.paginate("/repos"))
    assert len(items) == 2
'''

# ── tests/test_ctx.py ────────────────────────────────────────────────────────
FILES["tests/test_ctx.py"] = '''\
"""Tests for repository context resolution."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("url,expected_ws", [
    ("git@bitbucket.org:myws/myrepo.git", "myws"),
    ("git@bitbucket.org:myws/myrepo", "myws"),
    ("https://bitbucket.org/myws/myrepo.git", "myws"),
    ("https://user@bitbucket.org/myws/myrepo.git", "myws"),
    ("https://bitbucket.org/myws/myrepo", "myws"),
])
def test_parse_remote_url_workspace(url: str, expected_ws: str) -> None:
    from bb.core.ctx import _parse_remote_url
    ref = _parse_remote_url(url)
    assert ref is not None and ref.workspace == expected_ws


@pytest.mark.parametrize("url,expected_slug", [
    ("git@bitbucket.org:myws/myrepo.git", "myrepo"),
    ("https://bitbucket.org/myws/myrepo.git", "myrepo"),
])
def test_parse_remote_url_slug(url: str, expected_slug: str) -> None:
    from bb.core.ctx import _parse_remote_url
    ref = _parse_remote_url(url)
    assert ref is not None and ref.slug == expected_slug


def test_bb_repo_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from bb.core.config import Settings
    from bb.core.ctx import current_repo
    s = Settings(default_workspace="", git_protocol="https", editor="")
    monkeypatch.setattr("bb.core.ctx.current_repo", lambda _: None)
    from bb.core.ctx import parse_repo_arg
    ref = parse_repo_arg("myws/myrepo")
    assert ref.full_name == "myws/myrepo"


def test_bad_format_raises() -> None:
    from bb.core.ctx import RepoContextError, parse_repo_arg
    with pytest.raises(RepoContextError):
        parse_repo_arg("badformat")


def test_full_name_property() -> None:
    from bb.core.ctx import RepoRef
    ref = RepoRef(workspace="acme", slug="rocket")
    assert ref.full_name == "acme/rocket"
'''

# ── tests/test_cli_smoke.py ──────────────────────────────────────────────────
FILES["tests/test_cli_smoke.py"] = '''\
"""Smoke tests: every command group responds to --help with exit 0."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

runner = CliRunner()


def test_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version_contains_version_string() -> None:
    from bb.main import app
    result = runner.invoke(app, ["--version"])
    assert "0.1.0" in result.output


def test_auth_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


def test_pr_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0


def test_repo_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["repo", "--help"])
    assert result.exit_code == 0


def test_api_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["api", "--help"])
    assert result.exit_code == 0


def test_config_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
'''

# ── write all files ───────────────────────────────────────────────────────────
for rel, content in FILES.items():
    dest = ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    print(f"  wrote {rel}")

print("\nAll files written.")

# Verify __version__ import
import sys
sys.path.insert(0, str(ROOT / "src"))
import importlib
bb = importlib.import_module("bb")
print(f"bb.__version__ = {bb.__version__!r}")
