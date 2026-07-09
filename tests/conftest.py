from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _disable_keyring_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests on the hosts.toml path unless a test opts into keyring."""
    monkeypatch.setattr("bb.core.auth._keyring_set", lambda *a, **k: False)
    monkeypatch.setattr("bb.core.auth._keyring_get", lambda *a, **k: None)
    monkeypatch.setattr("bb.core.auth._keyring_delete", lambda *a, **k: False)


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "bb_config"
    config_dir.mkdir()

    def _patched_hosts_path() -> Path:
        return config_dir / "hosts.toml"

    monkeypatch.setattr("bb.core.auth._hosts_path", _patched_hosts_path)
    return config_dir


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("BB_TOKEN", "BITBUCKET_TOKEN", "BITBUCKET_AUTH_TOKEN", "BB_REPO", "BB_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
