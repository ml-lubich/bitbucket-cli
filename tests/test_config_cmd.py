"""
test_config_cmd.py — Behaviour tests for `bb config` subcommands.

Isolation: conftest.isolate_bb_env handles tmp HOME, config dir, and env cleanup.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _patch_cfg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cfg = tmp_path / "config.toml"
    import bb.core.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: cfg)
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    return cfg


def test_config_set_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _patch_cfg(monkeypatch, tmp_path)
    runner.invoke(app, ["config", "set", "editor", "vim"])
    assert cfg.exists()


def test_config_set_prints_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "set", "editor", "vim"])
    assert "editor" in result.output


def test_config_get_returns_set_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    runner.invoke(app, ["config", "set", "editor", "nano"])
    result = runner.invoke(app, ["config", "get", "editor"])
    assert "nano" in result.output


def test_config_set_get_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    runner.invoke(app, ["config", "set", "git_protocol", "ssh"])
    result = runner.invoke(app, ["config", "get", "git_protocol"])
    assert result.exit_code == 0


def test_config_get_unknown_key_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "get", "unknown_key"])
    assert result.exit_code != 0


def test_config_set_unknown_key_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "set", "unknown_key", "val"])
    assert result.exit_code != 0
