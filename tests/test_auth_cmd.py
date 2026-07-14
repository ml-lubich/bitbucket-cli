"""
test_auth_cmd.py — Behaviour tests for `bb auth` subcommands and completion.

Isolation: conftest.isolate_bb_env handles tmp HOME, config dir, and env cleanup.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner, _NamedTextIOWrapper

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


# ── login routing: OAuth / DC / non-TTY ──────────────────────────────────────

def _patch_cfg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate config.toml lookups from the real machine's user config dir —
    otherwise a Data-Center base_url configured on the host would leak in."""
    import bb.core.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")


def _patch_tty(monkeypatch: pytest.MonkeyPatch, *, isatty: bool = True) -> None:
    """CliRunner swaps sys.stdin for its own _NamedTextIOWrapper on each
    invoke(); patch isatty() on that class (not the module-level sys.stdin
    object, which gets replaced) so sys.stdin.isatty() reflects `isatty`
    inside the command under test."""
    monkeypatch.setattr(_NamedTextIOWrapper, "isatty", lambda self: isatty)


def test_login_cloud_no_flags_non_tty_exits_1_with_fallback_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert "--with-token" in result.output or "BB_TOKEN" in result.output


def test_login_cloud_tty_no_flags_uses_oauth_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    from bb.core.oauth import TokenResponse

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    _patch_tty(monkeypatch)
    monkeypatch.setattr(auth_cmd, "_verify_user", lambda cred, deployment=None: "oauth-user")

    called: dict[str, object] = {}

    def fake_run_loopback_login(client: object, **kwargs: object) -> TokenResponse:
        called["client"] = client
        return TokenResponse(access_token="oauth-access", refresh_token="oauth-refresh", expires_in=7200)

    import bb.core.oauth as oauth_mod
    monkeypatch.setattr(oauth_mod, "run_loopback_login", fake_run_loopback_login)
    monkeypatch.setenv("BB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("BB_OAUTH_CLIENT_SECRET", "secret")

    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0
    assert "oauth-user" in result.output
    assert called  # run_loopback_login was invoked
    assert "oauth-access" not in result.output
    assert "oauth-refresh" not in result.output


def test_login_cloud_tty_saves_oauth_credential_with_refresh_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.commands.auth as auth_cmd
    import bb.core.auth as auth_mod
    from bb.core.oauth import TokenResponse

    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    _patch_cfg(monkeypatch, tmp_path)
    _patch_tty(monkeypatch)
    monkeypatch.setattr(auth_cmd, "_verify_user", lambda cred, deployment=None: "oauth-user")

    import bb.core.oauth as oauth_mod
    monkeypatch.setattr(
        oauth_mod,
        "run_loopback_login",
        lambda client, **kw: TokenResponse(access_token="at", refresh_token="rt", expires_in=7200),
    )
    monkeypatch.setenv("BB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("BB_OAUTH_CLIENT_SECRET", "secret")

    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0
    stored = auth_mod._cred_from_file("bitbucket.org")
    assert stored is not None
    assert stored.auth_type == "oauth"
    assert stored.refresh_token == "rt"
    assert stored.expires_at > 0


def test_login_oauth_client_unresolved_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    _patch_tty(monkeypatch)
    monkeypatch.delenv("BB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("BB_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(oauth_mod, "_EMBEDDED_CLIENT_ID", "")
    monkeypatch.setattr(oauth_mod, "_EMBEDDED_CLIENT_SECRET", "")

    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1


def test_login_datacenter_no_flags_tty_prompts_never_sso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    import bb.core.oauth as oauth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    _patch_tty(monkeypatch)

    def _fail(*a: object, **k: object) -> None:
        raise AssertionError("SSO/browser flow must never run for Data Center")

    monkeypatch.setattr(oauth_mod, "run_loopback_login", _fail)

    result = runner.invoke(
        app,
        ["auth", "login", "--base-url", "https://bitbucket.polariswireless.com", "--no-verify"],
        input="dc-token\n",
    )
    assert "Data Center requires a token" in result.output
    assert result.exit_code == 0


def test_login_datacenter_no_flags_non_tty_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    result = runner.invoke(
        app, ["auth", "login", "--base-url", "https://bitbucket.polariswireless.com"]
    )
    assert result.exit_code == 1
    assert "Data Center requires a token" in result.output


# ── auth refresh / setup-git ─────────────────────────────────────────────────

def test_auth_refresh_forces_refresh_and_prints_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    from bb.core.auth import Credential
    from bb.core.oauth import TokenResponse

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    auth_mod.save_credential(
        Credential(token="old", auth_type="oauth", refresh_token="old-refresh")
    )

    import bb.core.oauth as oauth_mod
    monkeypatch.setattr(oauth_mod, "resolve_oauth_client", lambda: oauth_mod.OAuthClient("cid", "secret"))
    monkeypatch.setattr(
        oauth_mod,
        "refresh_access_token",
        lambda client, refresh_token, **kw: TokenResponse(access_token="new", refresh_token="new-r", expires_in=100),
    )
    result = runner.invoke(app, ["auth", "refresh"])
    assert result.exit_code == 0
    assert "refreshed" in result.output.lower()


def test_auth_refresh_non_oauth_login_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    from bb.core.auth import Credential

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    auth_mod.save_credential(Credential(token="tok"))
    result = runner.invoke(app, ["auth", "refresh"])
    assert result.exit_code == 1


def test_auth_refresh_no_credential_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    result = runner.invoke(app, ["auth", "refresh"])
    assert result.exit_code == 1


def test_auth_setup_git_prints_config_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    from bb.core.auth import Credential

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    auth_mod.save_credential(Credential(token="git-tok"))
    result = runner.invoke(app, ["auth", "setup-git"])
    assert result.exit_code == 0
    assert "http.extraHeader" in result.output
    # setup-git's whole purpose is emitting the auth header for git config —
    # the token belongs in this output (unlike OAuth flow logs/HTML).
    assert "git-tok" in result.output


def test_auth_setup_git_no_credential_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    _patch_cfg(monkeypatch, tmp_path)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    result = runner.invoke(app, ["auth", "setup-git"])
    assert result.exit_code == 1


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
