"""Additional auth command edge coverage."""
from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _patch_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")


def test_login_datacenter_no_verify_saves_host_and_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "auth",
            "login",
            "--base-url",
            "https://bitbucket.polariswireless.com",
            "--token",
            "tok",
            "--no-verify",
        ],
    )
    assert result.exit_code == 0
    doc = tomlkit.parse((tmp_path / "hosts.toml").read_text())
    assert "bitbucket.polariswireless.com" in doc
    cfg = tomlkit.parse((tmp_path / "config.toml").read_text())
    assert cfg["base_url"] == "https://bitbucket.polariswireless.com"


def test_login_basic_requires_username(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "login", "--token", "tok", "--auth-type", "basic"])
    assert result.exit_code == 1


def test_login_basic_with_username_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "auth",
            "login",
            "--token",
            "ATATT-secret",
            "--username",
            "user@example.com",
            "--no-verify",
        ],
    )
    assert result.exit_code == 0
    doc = tomlkit.parse((tmp_path / "hosts.toml").read_text())
    entry = doc["bitbucket.org"]
    assert entry["auth_type"] == "basic"
    assert entry["username"] == "user@example.com"


def test_login_invalid_auth_type_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "login", "--token", "tok", "--auth-type", "oauth"])
    assert result.exit_code == 1


def test_login_empty_token_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "login"], input="\n")
    assert result.exit_code == 1


def test_login_with_token_from_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "login", "--with-token", "--no-verify"], input="stdin-tok\n")
    assert result.exit_code == 0
    doc = tomlkit.parse((tmp_path / "hosts.toml").read_text())
    assert doc["bitbucket.org"]["token"] == "stdin-tok"


def test_login_rejects_token_and_with_token_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "login", "--token", "tok", "--with-token"])
    assert result.exit_code == 1


def test_logout_without_credentials_prints_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_files(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "logout"])
    assert "no credentials stored" in result.output


def test_status_rejected_token_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.commands.auth as auth_cmd
    from bb.core.errors import ApiError

    _patch_files(monkeypatch, tmp_path)
    monkeypatch.setenv("BB_TOKEN", "badtok")

    def _reject(cred: object, deployment: object = None) -> str:
        raise ApiError(401, "Unauthorized")

    monkeypatch.setattr(auth_cmd, "_verify_user", _reject)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 1


def test_auth_token_prints_raw_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_files(monkeypatch, tmp_path)
    monkeypatch.setenv("BB_TOKEN", "raw-secret-token")
    result = runner.invoke(app, ["auth", "token"])
    assert result.exit_code == 0
    assert result.output.strip() == "raw-secret-token"


def test_auth_login_help_mentions_keyring() -> None:
    result = runner.invoke(app, ["auth", "login", "--help"])
    assert result.exit_code == 0
    assert "keyring" in result.output.lower()
    assert "--with-token" in result.output
    assert "--web" not in result.output


def test_login_stores_in_keyring_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod

    _patch_files(monkeypatch, tmp_path)
    store: dict[str, dict[str, str]] = {}

    def _set(host: str, token: str, meta: dict[str, str]) -> bool:
        store[host] = {"token": token, **meta}
        return True

    def _get(host: str) -> dict[str, str] | None:
        return store.get(host)

    monkeypatch.setattr(auth_mod, "_keyring_set", _set)
    monkeypatch.setattr(auth_mod, "_keyring_get", _get)
    result = runner.invoke(app, ["auth", "login", "--token", "kr-tok", "--no-verify"])
    assert result.exit_code == 0
    assert store["bitbucket.org"]["token"] == "kr-tok"
    doc = tomlkit.parse((tmp_path / "hosts.toml").read_text())
    assert "token" not in doc["bitbucket.org"]
    assert doc["bitbucket.org"]["storage"] == "keyring"
