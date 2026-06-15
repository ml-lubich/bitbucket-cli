"""
test_api_cmd.py — Behaviour tests for the gh-style `bb api <endpoint>` command.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _mock_raw(monkeypatch: pytest.MonkeyPatch, text: str) -> list[tuple[str, str, str]]:
    calls: list[tuple[str, str, str]] = []

    def fake_raw(method: str, path: str, fields: dict[str, str] | None = None, body: str = "") -> str:
        calls.append((method, path, body))
        return text

    monkeypatch.setattr("bb.commands.api._client_mod.raw_request", fake_raw)
    return calls


def test_api_pretty_prints_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, '{"key": "value"}')
    result = runner.invoke(app, ["api", "/user"])
    assert '"key"' in result.output


def test_api_output_is_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, '{"a": 1}')
    result = runner.invoke(app, ["api", "/user"])
    assert json.loads(result.output)["a"] == 1


def test_api_non_json_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, "plain text log")
    result = runner.invoke(app, ["api", "/x/log"])
    assert "plain text log" in result.output


def test_api_exit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, "{}")
    result = runner.invoke(app, ["api", "/user"])
    assert result.exit_code == 0


def test_api_post_fields_become_body(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_raw(monkeypatch, "{}")
    runner.invoke(app, ["api", "/repos", "-X", "POST", "-f", "name=demo"])
    assert calls[0] == ("POST", "/repos", '{"name": "demo"}')


def test_api_malformed_field_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, "{}")
    result = runner.invoke(app, ["api", "/user", "-f", "noequals"], catch_exceptions=True)
    assert result.exit_code != 0


def test_api_input_and_field_exclusive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_raw(monkeypatch, "{}")
    payload = tmp_path / "body.json"
    payload.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app, ["api", "/x", "--input", str(payload), "-f", "a=b"], catch_exceptions=True
    )
    assert result.exit_code != 0


def test_api_input_file_is_body(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _mock_raw(monkeypatch, "{}")
    payload = tmp_path / "body.json"
    payload.write_text('{"x": 1}', encoding="utf-8")
    runner.invoke(app, ["api", "/x", "-X", "PUT", "--input", str(payload)])
    assert calls[0][2] == '{"x": 1}'


def test_api_help_exits_zero() -> None:
    result = runner.invoke(app, ["api", "--help"])
    assert result.exit_code == 0
