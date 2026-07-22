"""Tests for bb.core.auth credential persistence (hosts.toml)."""
from __future__ import annotations

import os
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
    if os.name != "nt":  # POSIX 0600 mode is not applicable on Windows (NTFS ACLs)
        assert oct(stat.S_IMODE(hosts.stat().st_mode)) == "0o600"


def test_delete_credential_removes_entry(tmp_config_dir: Path) -> None:
    from bb.core.auth import Credential, delete_credential, save_credential, stored_credential
    from bb.core.errors import AuthError
    save_credential(Credential(token="tok"))
    delete_credential()
    with pytest.raises((AuthError, Exception)):
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
    with pytest.raises((AuthError, Exception)):
        stored_credential()
