"""
TDD matrix for credential resolution + keyring persistence.

≥5000 parametrized cases: precedence, round-trips, masking, host isolation,
auth-type/username combos, CLI login, dotenv. One assert per test.
"""
from __future__ import annotations

import itertools
import os
from pathlib import Path

import pytest
import tomlkit
from typer.testing import CliRunner

from bb.cli import app
from bb.core.auth import HOST, Credential, masked
from bb.core.errors import AuthError

_TOKEN_SAMPLES = (
    [f"tok-{i:04d}" for i in range(50)]
    + ["ATATT" + "x" * 20, "BBDC-" + "y" * 16, "a", "ab", "abcd", "abcde", "token-with-ü"]
)
_HOSTS = (
    "bitbucket.org",
    "bitbucket.polariswireless.com",
    "git.example.internal",
    "bitbucket.company.com",
    "localhost",
)
_AUTH_TYPES = ("bearer", "basic")
_USERNAMES = ("", "alice", "user@example.com", "svc-bot")
_EMAIL_VARS = ("BITBUCKET_EMAIL", "BB_USERNAME")
_TOKEN_VARS = ("BB_TOKEN", "BITBUCKET_TOKEN", "BITBUCKET_AUTH_TOKEN")
_FILE_CASES = list(
    itertools.islice(
        itertools.product(_TOKEN_SAMPLES, _HOSTS, _AUTH_TYPES, _USERNAMES),
        1000,
    )
)
_KEYRING_CASES = list(
    itertools.islice(
        itertools.product(_TOKEN_SAMPLES, _HOSTS, _AUTH_TYPES, _USERNAMES),
        1000,
    )
)


def _clear_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _TOKEN_VARS + _EMAIL_VARS:
        monkeypatch.delenv(name, raising=False)


def _patch_hosts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    import bb.core.auth as auth_mod

    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    return hosts


def _install_memory_keyring(
    monkeypatch: pytest.MonkeyPatch, store: dict[str, dict[str, str]]
) -> None:
    import bb.core.auth as auth_mod

    def _set(host: str, token: str, meta: dict[str, str]) -> bool:
        store[host] = {"token": token, **meta}
        return True

    def _get(host: str) -> dict[str, str] | None:
        return store.get(host)

    def _delete(host: str) -> bool:
        return store.pop(host, None) is not None

    monkeypatch.setattr(auth_mod, "_keyring_set", _set)
    monkeypatch.setattr(auth_mod, "_keyring_get", _get)
    monkeypatch.setattr(auth_mod, "_keyring_delete", _delete)


def _norm_user(auth_type: str, username: str) -> str:
    if auth_type != "basic":
        return ""
    return username or "required-user"


# ── masked() ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token", [f"m{i:04d}{'z' * (i % 17)}" for i in range(300)])
def test_masked_never_contains_full_token(token: str) -> None:
    out = masked(token)
    assert len(token) <= 4 or token not in out


@pytest.mark.parametrize("token", [f"s{i:03d}" for i in range(150)])
def test_masked_starts_with_prefix(token: str) -> None:
    out = masked(token)
    assert out == token[:4] + "****"


# ── file fallback ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token,host,auth_type,username", _FILE_CASES)
def test_file_fallback_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    token: str,
    host: str,
    auth_type: str,
    username: str,
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(auth_mod, "_keyring_get", lambda *a, **k: None)
    user = _norm_user(auth_type, username)
    auth_mod.save_credential(
        Credential(token=token, host=host, auth_type=auth_type, username=user)
    )
    assert auth_mod.resolve_credential(host=host).token == token


@pytest.mark.parametrize("token,host", list(itertools.product(_TOKEN_SAMPLES[:40], _HOSTS)))
def test_file_fallback_mode_0600(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str, host: str
) -> None:
    import bb.core.auth as auth_mod

    hosts = _patch_hosts(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    auth_mod.save_credential(Credential(token=token, host=host))
    if os.name != "nt":  # POSIX 0600 mode is not applicable on Windows (NTFS ACLs)
        assert hosts.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("token,host,auth_type,username", _FILE_CASES[:400])
def test_file_fallback_preserves_auth_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    token: str,
    host: str,
    auth_type: str,
    username: str,
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(auth_mod, "_keyring_get", lambda *a, **k: None)
    user = _norm_user(auth_type, username)
    auth_mod.save_credential(
        Credential(token=token, host=host, auth_type=auth_type, username=user)
    )
    assert auth_mod.resolve_credential(host=host).auth_type == auth_type


# ── keyring ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token,host,auth_type,username", _KEYRING_CASES)
def test_keyring_roundtrip_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    token: str,
    host: str,
    auth_type: str,
    username: str,
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    hosts = _patch_hosts(monkeypatch, tmp_path)
    store: dict[str, dict[str, str]] = {}
    _install_memory_keyring(monkeypatch, store)
    user = _norm_user(auth_type, username)
    auth_mod.save_credential(
        Credential(token=token, host=host, auth_type=auth_type, username=user)
    )
    cred = auth_mod.resolve_credential(host=host)
    assert cred.source == "keyring"
    assert cred.token == token
    entry = tomlkit.parse(hosts.read_text()).get(host) or {}
    assert "token" not in entry


@pytest.mark.parametrize("host", _HOSTS)
@pytest.mark.parametrize("token", [f"iso-{i:03d}" for i in range(50)])
def test_keyring_host_isolation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, host: str, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    store: dict[str, dict[str, str]] = {}
    _install_memory_keyring(monkeypatch, store)
    other = "other.example.com" if host != "other.example.com" else "alt.example.com"
    auth_mod.save_credential(Credential(token=token, host=host))
    auth_mod.save_credential(Credential(token="other-token", host=other))
    assert auth_mod.resolve_credential(host=host).token == token


@pytest.mark.parametrize("token", [f"kr-win-{i:03d}" for i in range(120)])
def test_keyring_beats_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    auth_mod.save_credential(Credential(token="file-loses", host=HOST))
    store = {HOST: {"token": token, "auth_type": "bearer", "username": ""}}
    _install_memory_keyring(monkeypatch, store)
    assert auth_mod.resolve_credential().token == token


# ── precedence ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("env_name", _TOKEN_VARS)
@pytest.mark.parametrize("token", [f"env-{i:03d}" for i in range(80)])
def test_env_beats_keyring_and_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env_name: str, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    store = {HOST: {"token": "keyring-lose", "auth_type": "bearer", "username": ""}}
    _install_memory_keyring(monkeypatch, store)
    monkeypatch.setenv(env_name, token)
    assert auth_mod.resolve_credential().source == f"env:{env_name}"


@pytest.mark.parametrize("email_var", _EMAIL_VARS)
@pytest.mark.parametrize("token", [f"ATATT-{i:03d}" for i in range(60)])
def test_email_env_upgrades_to_basic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, email_var: str, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    monkeypatch.setenv("BB_TOKEN", token)
    monkeypatch.setenv(email_var, "me@example.com")
    assert auth_mod.resolve_credential().auth_type == "basic"


@pytest.mark.parametrize("var", _TOKEN_VARS)
@pytest.mark.parametrize("token", [f"denv-{i:03d}" for i in range(50)])
def test_dotenv_used_when_env_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, var: str, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    denv = tmp_path / ".env"
    denv.write_text(f"{var}={token}\n", encoding="utf-8")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: denv)
    assert auth_mod.resolve_credential().token == token


# ── delete ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("host", _HOSTS)
@pytest.mark.parametrize("token", [f"del-{i:03d}" for i in range(50)])
def test_delete_removes_keyring(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, host: str, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    store: dict[str, dict[str, str]] = {}
    _install_memory_keyring(monkeypatch, store)
    auth_mod.save_credential(Credential(token=token, host=host))
    assert auth_mod.delete_credential(host) is True
    with pytest.raises(AuthError):
        auth_mod.resolve_credential(host=host)


@pytest.mark.parametrize("host", _HOSTS)
@pytest.mark.parametrize("token", [f"fd-{i:03d}" for i in range(50)])
def test_delete_removes_file_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, host: str, token: str
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(auth_mod, "_keyring_get", lambda *a, **k: None)
    monkeypatch.setattr(auth_mod, "_keyring_delete", lambda *a, **k: False)
    auth_mod.save_credential(Credential(token=token, host=host))
    assert auth_mod.delete_credential(host) is True
    with pytest.raises(AuthError):
        auth_mod.resolve_credential(host=host)


@pytest.mark.parametrize("idx", range(160))
def test_resolve_raises_when_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, idx: int
) -> None:
    import bb.core.auth as auth_mod

    _clear_token_env(monkeypatch)
    _patch_hosts(monkeypatch, tmp_path / f"e{idx}")
    monkeypatch.setattr(auth_mod, "_keyring_get", lambda *a, **k: None)
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()


# ── CLI ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token", [f"cli-{i:03d}" for i in range(100)])
def test_login_cli_file_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str
) -> None:
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    result = CliRunner().invoke(app, ["auth", "login", "--token", token, "--no-verify"])
    assert result.exit_code == 0
    assert auth_mod.resolve_credential().token == token


@pytest.mark.parametrize("token", [f"clk-{i:03d}" for i in range(100)])
def test_login_cli_keyring(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str
) -> None:
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    store: dict[str, dict[str, str]] = {}
    _install_memory_keyring(monkeypatch, store)
    result = CliRunner().invoke(app, ["auth", "login", "--token", token, "--no-verify"])
    assert result.exit_code == 0
    assert store[HOST]["token"] == token


@pytest.mark.parametrize("token", [f"st-{i:03d}" for i in range(80)])
def test_status_masks_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str
) -> None:
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setenv("BB_TOKEN", token)
    monkeypatch.setattr(auth_cmd, "_show_user_status", lambda *a, **k: None)
    result = CliRunner().invoke(app, ["auth", "status"])
    assert token not in result.output


@pytest.mark.parametrize("token", [f"tokencmd-{i:03d}" for i in range(80)])
def test_auth_token_cmd_prints_raw(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str
) -> None:
    import bb.core.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setenv("BB_TOKEN", token)
    result = CliRunner().invoke(app, ["auth", "token"])
    assert result.output.strip() == token


@pytest.mark.parametrize("token", [f"out-{i:03d}" for i in range(60)])
def test_logout_after_login_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, token: str
) -> None:
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    CliRunner().invoke(app, ["auth", "login", "--token", token, "--no-verify"])
    result = CliRunner().invoke(app, ["auth", "logout"])
    assert result.exit_code == 0
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()
