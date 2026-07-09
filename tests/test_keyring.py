"""Tests for OS keyring credential storage."""
from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit

from bb.core.auth import Credential
from bb.core.errors import AuthError


def test_save_credential_prefers_keyring(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import bb.core.auth as auth_mod

    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    store: dict[str, dict[str, str]] = {}

    monkeypatch.setattr(
        auth_mod,
        "_keyring_set",
        lambda host, token, meta: store.update({host: {"token": token, **meta}}) or True,
    )
    monkeypatch.setattr(auth_mod, "_keyring_get", lambda host: store.get(host))
    monkeypatch.setattr(auth_mod, "_keyring_delete", lambda host: store.pop(host, None) is not None)

    auth_mod.save_credential(Credential(token="secret", auth_type="bearer"))
    assert store["bitbucket.org"]["token"] == "secret"
    doc = tomlkit.parse(hosts.read_text())
    assert doc["bitbucket.org"]["storage"] == "keyring"
    assert "token" not in doc["bitbucket.org"]


def test_resolve_credential_from_keyring(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import bb.core.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(auth_mod, "_find_dotenv", lambda: None)
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        auth_mod,
        "_keyring_get",
        lambda host: {"token": "kr-tok", "auth_type": "bearer", "username": ""},
    )
    cred = auth_mod.resolve_credential()
    assert cred.source == "keyring"
    assert cred.token == "kr-tok"


def test_delete_credential_clears_keyring(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import bb.core.auth as auth_mod

    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    store = {"bitbucket.org": {"token": "tok", "auth_type": "bearer", "username": ""}}

    monkeypatch.setattr(auth_mod, "_keyring_get", lambda host: store.get(host))
    monkeypatch.setattr(
        auth_mod,
        "_keyring_delete",
        lambda host: store.pop(host, None) is not None,
    )
    hosts.write_text('["bitbucket.org"]\nstorage = "keyring"\nauth_type = "bearer"\n')
    assert auth_mod.delete_credential() is True
    assert "bitbucket.org" not in store
    assert not hosts.exists()


def test_keyring_fallback_to_file_when_set_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import bb.core.auth as auth_mod

    hosts = tmp_path / "hosts.toml"
    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: hosts)
    monkeypatch.setattr(auth_mod, "_keyring_set", lambda *a, **k: False)
    auth_mod.save_credential(Credential(token="file-tok"))
    doc = tomlkit.parse(hosts.read_text())
    assert doc["bitbucket.org"]["token"] == "file-tok"
    assert doc["bitbucket.org"]["storage"] == "file"


def test_stored_credential_raises_when_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import bb.core.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    with pytest.raises(AuthError):
        auth_mod.stored_credential()
