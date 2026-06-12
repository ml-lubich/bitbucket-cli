from __future__ import annotations

from pathlib import Path

import pytest


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
    for key in ("BB_TOKEN", "BITBUCKET_TOKEN", "BITBUCKET_AUTH_TOKEN", "BB_REPO"):
        monkeypatch.delenv(key, raising=False)
