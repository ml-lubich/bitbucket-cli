"""
test_auth_cmd.py — Behaviour tests for `bb auth` subcommands and completion.

Isolation: conftest.isolate_bb_env handles tmp HOME, config dir, and env cleanup.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_success_saves_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    runner.invoke(app, ["auth", "login", "--token", "mytoken123", "--no-verify"])
    assert (tmp_path / "hosts.toml").exists()


def test_login_success_prints_display_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_cmd, "_verify_user", lambda cred: "alice")
    result = runner.invoke(app, ["auth", "login", "--token", "mytoken123"])
    assert "alice" in result.output


def test_login_rejected_token_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    from bb.core.errors import ApiError
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")

    def _reject(cred: object) -> str:
        raise ApiError(401, "Unauthorized")

    monkeypatch.setattr(auth_cmd, "_verify_user", _reject)
    result = runner.invoke(app, ["auth", "login", "--token", "badtoken"])
    assert result.exit_code != 0


def test_login_rejected_token_does_not_save_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    from bb.core.errors import ApiError
    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)

    def _reject(cred: object) -> str:
        raise ApiError(401, "Unauthorized")

    monkeypatch.setattr(auth_cmd, "_verify_user", _reject)
    runner.invoke(app, ["auth", "login", "--token", "badtoken"])
    assert not hosts.exists()


# ── status ────────────────────────────────────────────────────────────────────

def test_status_raw_token_not_in_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BB_TOKEN", "supersecrettoken")
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_cmd, "_show_user_status", lambda cred: None)
    result = runner.invoke(app, ["auth", "status"])
    assert "supersecrettoken" not in result.output


def test_status_with_no_auth_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 1


def test_status_shows_masked_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "abcdefghij")
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_cmd, "_show_user_status", lambda cred: None)
    result = runner.invoke(app, ["auth", "status"])
    assert "abcd****" in result.output


# ── .env file provides token ──────────────────────────────────────────────────

def test_dotenv_provides_bitbucket_auth_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dot_env = tmp_path / ".env"
    dot_env.write_text("BITBUCKET_AUTH_TOKEN=tokenFromDotEnv\n")
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: dot_env)
    monkeypatch.setattr(auth_cmd, "_show_user_status", lambda cred: None)
    result = runner.invoke(app, ["auth", "status"])
    assert "dotenv:BITBUCKET_AUTH_TOKEN" in result.output


# ── completion ────────────────────────────────────────────────────────────────

def test_completion_zsh_exits_zero() -> None:
    result = runner.invoke(app, ["completion", "zsh"])
    assert result.exit_code == 0


def test_completion_zsh_contains_bb_complete() -> None:
    result = runner.invoke(app, ["completion", "zsh"])
    assert "_BB_COMPLETE" in result.output


def test_completion_unknown_shell_exits_nonzero() -> None:
    result = runner.invoke(app, ["completion", "fish2"])
    assert result.exit_code != 0
