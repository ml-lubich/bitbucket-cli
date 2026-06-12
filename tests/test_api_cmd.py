"""
test_api_cmd.py — Behaviour tests for `bb api` command.

Isolation: conftest.isolate_bb_env handles tmp HOME, config dir, and env cleanup.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _set_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "testtoken")


def _mock_raw(monkeypatch: pytest.MonkeyPatch, response: str) -> None:
    # api.py calls _client.raw_request where _client is bb.core.client module
    import bb.core.client as client_mod
    monkeypatch.setattr(client_mod, "raw_request", lambda *a, **kw: response)


def test_api_pretty_prints_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch)
    _mock_raw(monkeypatch, '{"key": "value"}')
    result = runner.invoke(app, ["api", "/user"])
    assert '"key"' in result.output


def test_api_pretty_prints_with_indent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch)
    _mock_raw(monkeypatch, '{"a": 1}')
    result = runner.invoke(app, ["api", "/user"])
    parsed = json.loads(result.output)
    assert parsed["a"] == 1


def test_api_non_json_response_printed_as_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_token(monkeypatch)
    _mock_raw(monkeypatch, "plain text response")
    result = runner.invoke(app, ["api", "/user"])
    assert "plain text response" in result.output


def test_api_field_and_input_mutually_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_token(monkeypatch)
    _mock_raw(monkeypatch, "{}")
    input_file = tmp_path / "body.json"
    input_file.write_text('{"x": 1}')
    result = runner.invoke(app, ["api", "/user", "-f", "key=val", "--input", str(input_file)])
    assert result.exit_code != 0


def test_api_field_malformed_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_token(monkeypatch)
    _mock_raw(monkeypatch, "{}")
    result = runner.invoke(app, ["api", "/user", "-f", "noequals"])
    assert result.exit_code != 0
