from __future__ import annotations

import stat
from pathlib import Path

import pytest

from bb.core.auth import Credential
from bb.core.errors import AuthError


def _make_hosts(tmp_path: Path, token: str = "stored-token", username: str = "user1") -> Path:
    hosts = tmp_path / "hosts.toml"
    hosts.write_text(f'["bitbucket.org"]\ntoken = "{token}"\nusername = "{username}"\n')
    return hosts


def test_bb_token_env_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("BB_TOKEN", "test-token-123")
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    cred = auth_mod.resolve_credential()
    assert cred.source == "env:BB_TOKEN"


def test_bitbucket_token_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_TOKEN", "test-token-456")
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    cred = auth_mod.resolve_credential()
    assert cred.source == "env:BITBUCKET_TOKEN"


def test_bitbucket_auth_token_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_AUTH_TOKEN", "test-token-789")
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    cred = auth_mod.resolve_credential()
    assert cred.source == "env:BITBUCKET_AUTH_TOKEN"


def test_hosts_toml_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    hosts = _make_hosts(tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    cred = auth_mod.resolve_credential()
    assert cred.source == "hosts"


def test_no_token_raises_auth_error(monkeypatch, tmp_path):
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()


def test_save_credential_creates_file(monkeypatch, tmp_path):
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    cred = Credential(token="test-token-abc", username="alice")
    auth_mod.save_credential(cred)
    assert (tmp_path / "hosts.toml").exists()


def test_save_credential_mode_0600(monkeypatch, tmp_path):
    import bb.core.auth as auth_mod
    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    cred = Credential(token="test-token-abc", username="alice")
    auth_mod.save_credential(cred)
    mode = stat.S_IMODE(hosts.stat().st_mode)
    assert mode == 0o600


def test_delete_credential_removes_entry(monkeypatch, tmp_path):
    import bb.core.auth as auth_mod
    hosts = _make_hosts(tmp_path)
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    result = auth_mod.delete_credential("bitbucket.org")
    assert result is True


def test_dot_env_loaded_for_token(monkeypatch, tmp_path):
    dot_env = tmp_path / ".env"
    dot_env.write_text('BB_TOKEN="test-token-xyz"\n')
    monkeypatch.delenv("BB_TOKEN", raising=False)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: dot_env)
    cred = auth_mod.resolve_credential()
    assert cred.source == "dotenv:BB_TOKEN"


def test_dot_env_does_not_override_env(monkeypatch, tmp_path):
    dot_env = tmp_path / ".env"
    dot_env.write_text("BB_TOKEN=from-dotenv\n")
    monkeypatch.setenv("BB_TOKEN", "from-env")
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: dot_env)
    cred = auth_mod.resolve_credential()
    assert cred.source == "env:BB_TOKEN"
