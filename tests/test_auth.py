"""Tests for bb.core.auth — credential resolution, persistence, and legacy API."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from bb.core.auth import Credential, Credentials
from bb.core.errors import AuthError

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _patch_hosts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hosts = tmp_path / "hosts.toml"
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    return hosts


def _make_hosts(tmp_path: Path, token: str = "stored-token", username: str = "user1") -> Path:
    hosts = tmp_path / "hosts.toml"
    hosts.write_text(f'["bitbucket.org"]\ntoken = "{token}"\nusername = "{username}"\n')
    return hosts


# ── resolve_credential: env var precedence ────────────────────────────────────

def test_bb_token_env_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BB_TOKEN", "test-token-123")
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    assert auth_mod.resolve_credential().source == "env:BB_TOKEN"


def test_bitbucket_token_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_TOKEN", "test-token-456")
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    assert auth_mod.resolve_credential().source == "env:BITBUCKET_TOKEN"


def test_bitbucket_auth_token_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_AUTH_TOKEN", "test-token-789")
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    assert auth_mod.resolve_credential().source == "env:BITBUCKET_AUTH_TOKEN"


def test_hosts_toml_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    hosts = _make_hosts(tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    assert auth_mod.resolve_credential().source == "hosts"


def test_no_token_raises_auth_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()


def test_resolve_credential_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setenv("BB_TOKEN", "env-tok")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    _patch_hosts(monkeypatch, tmp_path)
    assert auth_mod.resolve_credential().token == "env-tok"


def test_resolve_credential_from_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    _patch_hosts(monkeypatch, tmp_path)
    auth_mod.save_credential(Credential(token="file-tok"))
    assert auth_mod.resolve_credential().token == "file-tok"


def test_resolve_credential_raises_when_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    _patch_hosts(monkeypatch, tmp_path)
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()


# ── dotenv ────────────────────────────────────────────────────────────────────

def test_dot_env_loaded_for_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dot_env = tmp_path / ".env"
    dot_env.write_text('BB_TOKEN="test-token-xyz"\n')
    monkeypatch.delenv("BB_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: dot_env)
    assert auth_mod.resolve_credential().source == "dotenv:BB_TOKEN"


def test_dot_env_does_not_override_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dot_env = tmp_path / ".env"
    dot_env.write_text("BB_TOKEN=from-dotenv\n")
    monkeypatch.setenv("BB_TOKEN", "from-env")
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: dot_env)
    assert auth_mod.resolve_credential().source == "env:BB_TOKEN"


def test_denv_token_returns_none_when_no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    assert auth_mod._denv_token() is None


def test_env_token_priority_bb_first(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setenv("BB_TOKEN", "bb")
    monkeypatch.setenv("BITBUCKET_TOKEN", "bt")
    cred = auth_mod._env_token()
    assert cred is not None and cred.token == "bb"


# ── save / delete / stored credential ────────────────────────────────────────

def test_save_credential_creates_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    auth_mod.save_credential(Credential(token="test-token-abc", username="alice"))
    assert (tmp_path / "hosts.toml").exists()


def test_save_credential_mode_0600(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    auth_mod.save_credential(Credential(token="test-token-abc", username="alice"))
    if os.name != "nt":  # POSIX 0600 mode is not applicable on Windows (NTFS ACLs)
        assert stat.S_IMODE(hosts.stat().st_mode) == 0o600


def test_delete_credential_removes_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    hosts = _make_hosts(tmp_path)
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    assert auth_mod.delete_credential("bitbucket.org") is True


def test_stored_credential_raises_when_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    with pytest.raises(AuthError):
        auth_mod.stored_credential()


def test_stored_credential_returns_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credential(Credential(token="stored-tok"))
    assert auth_mod.stored_credential().token == "stored-tok"


def test_save_credential_sets_auth_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credential(Credential(token="tok", auth_type="basic", username="alice"))
    assert auth_mod.stored_credential().auth_type == "basic"


# ── masked ────────────────────────────────────────────────────────────────────

def test_masked_shows_first_four() -> None:
    from bb.core.auth import masked
    assert masked("abcdefgh").startswith("abcd")


def test_masked_hides_rest() -> None:
    from bb.core.auth import masked
    assert "efgh" not in masked("abcdefgh")


# ── hosts.toml store (tmp_config_dir fixture) ─────────────────────────────────

def test_store_token_creates_file(tmp_config_dir: Path) -> None:
    from bb.core.auth import save_credential
    save_credential(Credential(token="my-secret-token"))
    assert (tmp_config_dir / "hosts.toml").is_file()


def test_read_token_returns_stored(tmp_config_dir: Path) -> None:
    from bb.core.auth import save_credential, stored_credential
    save_credential(Credential(token="my-secret-token"))
    assert stored_credential().token == "my-secret-token"


def test_file_mode_is_0600(tmp_config_dir: Path) -> None:
    from bb.core.auth import save_credential
    save_credential(Credential(token="tok"))
    hosts = tmp_config_dir / "hosts.toml"
    if os.name != "nt":  # POSIX 0600 mode is not applicable on Windows (NTFS ACLs)
        assert oct(stat.S_IMODE(hosts.stat().st_mode)) == "0o600"


def test_delete_credential_removes_entry_via_fixture(tmp_config_dir: Path) -> None:
    from bb.core.auth import delete_credential, save_credential, stored_credential
    save_credential(Credential(token="tok"))
    delete_credential()
    with pytest.raises((AuthError, Exception)):
        stored_credential()


def test_delete_returns_true_when_present(tmp_config_dir: Path) -> None:
    from bb.core.auth import delete_credential, save_credential
    save_credential(Credential(token="tok"))
    assert delete_credential() is True


def test_delete_returns_false_when_absent(tmp_config_dir: Path) -> None:
    from bb.core.auth import delete_credential
    assert delete_credential() is False


def test_read_raises_when_no_file(tmp_config_dir: Path) -> None:
    from bb.core.auth import stored_credential
    with pytest.raises((AuthError, Exception)):
        stored_credential()


# ── token precedence (test_cfg.py coverage) ──────────────────────────────────

def test_bb_token_beats_bitbucket_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "bb-tok")
    monkeypatch.setenv("BITBUCKET_TOKEN", "other-tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    assert resolve_credential().token == "bb-tok"


def test_bitbucket_token_used_when_no_bb_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_TOKEN", "bt-tok")
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    monkeypatch.setattr("bb.core.auth._denv_token", lambda: None)
    from bb.core.auth import resolve_credential
    assert resolve_credential().token == "bt-tok"


def test_auth_token_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_AUTH_TOKEN", "auth-tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    monkeypatch.setattr("bb.core.auth._denv_token", lambda: None)
    from bb.core.auth import resolve_credential
    assert resolve_credential().token == "auth-tok"


def test_dotenv_fallback_reads_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("BB_TOKEN=dotenv-tok\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    assert resolve_credential().token == "dotenv-tok"


def test_source_reflects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    assert "BB_TOKEN" in resolve_credential().source


# ── legacy API ────────────────────────────────────────────────────────────────

def test_load_credentials_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_repo_root", lambda: None)
    monkeypatch.setenv("BB_TOKEN", "legacy-tok")
    assert auth_mod.load_credentials().token == "legacy-tok"


def test_credential_source_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_repo_root", lambda: None)
    monkeypatch.setenv("BB_TOKEN", "tok")
    assert auth_mod.credential_source().startswith("env:")


def test_credential_source_hosts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_repo_root", lambda: None)
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    auth_mod.save_credential(Credential(token="file-tok"))
    assert auth_mod.credential_source() == "hosts.toml"


def test_clear_credentials_removes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hosts = _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credential(Credential(token="tok"))
    assert hosts.exists()
    auth_mod.clear_credentials()
    assert not hosts.exists()


def test_save_credentials_legacy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hosts = _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credentials(Credentials(token="leg-tok", username="user"))
    assert hosts.exists()


def test_token_from_source_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setenv("BB_TOKEN", "src-tok")
    assert auth_mod._token_from_source("env:BB_TOKEN") == "src-tok"


def test_username_from_hosts_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    assert auth_mod._username_from_hosts() == ""


def test_email_env_upgrades_to_basic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod

    monkeypatch.setenv("BB_TOKEN", "ATATT-tok")
    monkeypatch.setenv("BITBUCKET_EMAIL", "me@example.com")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    cred = auth_mod.resolve_credential()
    assert cred.auth_type == "basic"
    assert cred.username == "me@example.com"


def test_corrupt_hosts_toml_falls_back_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hosts = _patch_hosts(monkeypatch, tmp_path)
    hosts.write_text("{not valid toml", encoding="utf-8")
    import bb.core.auth as auth_mod

    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()


def test_nested_hosts_toml_section(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hosts = _patch_hosts(monkeypatch, tmp_path)
    hosts.write_text(
        '[bitbucket.org]\ntoken = "nested-tok"\nauth_type = "bearer"\n',
        encoding="utf-8",
    )
    import bb.core.auth as auth_mod

    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    assert auth_mod.resolve_credential().token == "nested-tok"


def test_authorization_header_bearer() -> None:
    from bb.core.auth import authorization_header

    assert authorization_header(Credential(token="tok")) == "Bearer tok"


def test_authorization_header_basic() -> None:
    import base64

    from bb.core.auth import authorization_header

    header = authorization_header(Credential(token="tok", username="alice", auth_type="basic"))
    expected = base64.b64encode(b"alice:tok").decode()
    assert header == f"Basic {expected}"


def test_git_command_injects_https_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod

    monkeypatch.setenv("BB_TOKEN", "git-tok")
    cmd = auth_mod.git_command(["clone", "https://example/repo.git"], https_auth=True)
    assert cmd == [
        "git",
        "-c",
        "http.extraHeader=Authorization: Bearer git-tok",
        "clone",
        "https://example/repo.git",
    ]


def test_git_command_skips_auth_when_disabled() -> None:
    from bb.core.auth import git_command

    assert git_command(["status"]) == ["git", "status"]
