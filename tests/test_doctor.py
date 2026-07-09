"""Tests for the agent-friendly doctor command."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bb.cli import app
from bb.core.auth import Credential

runner = CliRunner()


def _patch_cfg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    monkeypatch.setattr(auth_mod, "_hosts_path", lambda: tmp_path / "hosts.toml")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")


def test_doctor_no_auth_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    result = runner.invoke(app, ["doctor", "--no-network"])
    assert result.exit_code == 1


def test_doctor_json_reports_datacenter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    cfg_mod.set_value("base_url", "https://bitbucket.polariswireless.com")
    auth_mod.save_credential(Credential(token="tok", host="bitbucket.polariswireless.com"))
    result = runner.invoke(app, ["doctor", "--json", "--no-network"])
    payload = json.loads(result.output)
    assert payload["provider"] == "datacenter"


def test_doctor_text_includes_base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    cfg_mod.set_value("base_url", "https://bitbucket.polariswireless.com")
    auth_mod.save_credential(Credential(token="tok", host="bitbucket.polariswireless.com"))
    result = runner.invoke(app, ["doctor", "--no-network"])
    assert "bitbucket.polariswireless.com" in result.output


def test_doctor_network_verify_called(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, tmp_path)
    import bb.commands.doctor as doctor_mod
    import bb.core.auth as auth_mod
    import bb.core.config as cfg_mod

    called: list[str] = []
    cfg_mod.set_value("base_url", "https://bitbucket.polariswireless.com")
    auth_mod.save_credential(Credential(token="tok", host="bitbucket.polariswireless.com"))
    monkeypatch.setattr(doctor_mod, "_verify", lambda deployment, cred: called.append(deployment.kind))
    result = runner.invoke(app, ["doctor"])
    assert called == ["datacenter"] and result.exit_code == 0
