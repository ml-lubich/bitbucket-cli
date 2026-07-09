"""Extended tests for bb.core.auth — covers resolve_credential, save/delete, _cred_from_file."""
from __future__ import annotations

from pathlib import Path

import pytest

from bb.core.auth import Credential
from bb.core.errors import AuthError


def _patch_hosts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hosts = tmp_path / "hosts.toml"
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    return hosts


def test_resolve_credential_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setenv("BB_TOKEN", "env-tok")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    _patch_hosts(monkeypatch, tmp_path)
    cred = auth_mod.resolve_credential()
    assert cred.token == "env-tok"


def test_resolve_credential_from_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    _patch_hosts(monkeypatch, tmp_path)
    auth_mod.save_credential(Credential(token="file-tok"))
    cred = auth_mod.resolve_credential()
    assert cred.token == "file-tok"


def test_resolve_credential_raises_when_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    _patch_hosts(monkeypatch, tmp_path)
    with pytest.raises(AuthError):
        auth_mod.resolve_credential()


def test_stored_credential_raises_when_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    with pytest.raises(AuthError):
        auth_mod.stored_credential()


def test_stored_credential_returns_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credential(Credential(token="stored-tok"))
    cred = auth_mod.stored_credential()
    assert cred.token == "stored-tok"


def test_save_credential_sets_auth_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credential(Credential(token="tok", auth_type="basic", username="alice"))
    cred = auth_mod.stored_credential()
    assert cred.auth_type == "basic"


def test_masked_shows_first_four() -> None:
    from bb.core.auth import masked
    assert masked("abcdefgh").startswith("abcd")


def test_masked_hides_rest() -> None:
    from bb.core.auth import masked
    assert "efgh" not in masked("abcdefgh")


def test_denv_token_returns_none_when_no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    result = auth_mod._denv_token()
    assert result is None


def test_env_token_priority_bb_first(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setenv("BB_TOKEN", "bb")
    monkeypatch.setenv("BITBUCKET_TOKEN", "bt")
    cred = auth_mod._env_token()
    assert cred is not None
    assert cred.token == "bb"


def test_load_credentials_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_repo_root", lambda: None)
    monkeypatch.setenv("BB_TOKEN", "legacy-tok")
    creds = auth_mod.load_credentials()
    assert creds.token == "legacy-tok"


def test_credential_source_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_repo_root", lambda: None)
    monkeypatch.setenv("BB_TOKEN", "tok")
    src = auth_mod.credential_source()
    assert src.startswith("env:")


def test_credential_source_hosts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bb.core.auth import Credentials
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_find_repo_root", lambda: None)
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    auth_mod.save_credentials(Credentials(token="file-tok"))
    src = auth_mod.credential_source()
    assert src == "hosts.toml"


def test_clear_credentials_removes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hosts = _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credential(Credential(token="tok"))
    assert hosts.exists()
    auth_mod.clear_credentials()
    assert not hosts.exists()


def test_save_credentials_legacy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bb.core.auth import Credentials
    hosts = _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    auth_mod.save_credentials(Credentials(token="leg-tok", username="user"))
    assert hosts.exists()


def test_token_from_source_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import bb.core.auth as auth_mod
    monkeypatch.setenv("BB_TOKEN", "src-tok")
    result = auth_mod._token_from_source("env:BB_TOKEN")
    assert result == "src-tok"


def test_username_from_hosts_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_hosts(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    result = auth_mod._username_from_hosts()
    assert result == ""
