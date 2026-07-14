"""
test_api_extended.py — gh-parity conveniences for `bb api`: --paginate, -f/-F, --jq.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest
from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def _mock_raw_sequence(
    monkeypatch: pytest.MonkeyPatch, responses: list[str]
) -> list[tuple[str, str, str]]:
    """Mock raw_request to return successive responses from `responses` per call."""
    calls: list[tuple[str, str, str]] = []
    state = {"i": 0}

    def fake_raw(
        method: str,
        path: str,
        fields: dict[str, str] | None = None,
        body: str = "",
        **_kwargs: Any,
    ) -> str:
        calls.append((method, path, body))
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        return responses[idx]

    monkeypatch.setattr("bb.commands.api._client_mod.raw_request", fake_raw)
    return calls


def _mock_raw(monkeypatch: pytest.MonkeyPatch, text: str) -> list[tuple[str, str, str]]:
    return _mock_raw_sequence(monkeypatch, [text])


# --- --paginate ---------------------------------------------------------


def test_paginate_joins_values_across_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    page1 = json.dumps({"values": [{"id": 1}, {"id": 2}], "next": "https://api.bitbucket.org/2.0/repositories/ws?page=2"})
    page2 = json.dumps({"values": [{"id": 3}]})
    calls = _mock_raw_sequence(monkeypatch, [page1, page2])
    result = runner.invoke(app, ["api", "/repositories/ws", "--paginate"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [v["id"] for v in data["values"]] == [1, 2, 3]
    assert len(calls) == 2
    # second call follows the absolute `next` URL
    assert calls[1][1] == "https://api.bitbucket.org/2.0/repositories/ws?page=2"


def test_paginate_stops_when_no_next(monkeypatch: pytest.MonkeyPatch) -> None:
    page1 = json.dumps({"values": [{"id": 1}]})
    calls = _mock_raw_sequence(monkeypatch, [page1])
    result = runner.invoke(app, ["api", "/repositories/ws", "--paginate"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [v["id"] for v in data["values"]] == [1]
    assert len(calls) == 1


def test_paginate_respects_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    page1 = json.dumps({"values": [{"id": 1}, {"id": 2}], "next": "https://x/y?page=2"})
    page2 = json.dumps({"values": [{"id": 3}, {"id": 4}]})
    _mock_raw_sequence(monkeypatch, [page1, page2])
    result = runner.invoke(app, ["api", "/repositories/ws", "--paginate", "--limit", "3"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [v["id"] for v in data["values"]] == [1, 2, 3]


def test_paginate_rejects_limit_below_one(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, json.dumps({"values": [{"id": 1}]}))
    result = runner.invoke(app, ["api", "/repositories/ws", "--paginate", "--limit", "0"])
    assert result.exit_code != 0
    assert "must be >= 1" in str(result.exception)


def test_paginate_single_non_paginated_response_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_raw(monkeypatch, '{"key": "value"}')
    result = runner.invoke(app, ["api", "/user", "--paginate"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"key": "value"}


def test_no_paginate_behaves_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, '{"key": "value"}')
    result = runner.invoke(app, ["api", "/user"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"key": "value"}


# --- -f/--raw-field and -F/--field --------------------------------------


def test_raw_field_short_flag_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_raw(monkeypatch, "{}")
    runner.invoke(app, ["api", "/repos", "-X", "POST", "-f", "name=demo"])
    assert calls[0] == ("POST", "/repos", '{"name": "demo"}')


def test_typed_field_coerces_bool_null_int(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_raw(monkeypatch, "{}")
    runner.invoke(
        app,
        [
            "api",
            "/repos",
            "-X",
            "POST",
            "-F",
            "active=true",
            "-F",
            "archived=false",
            "-F",
            "parent=null",
            "-F",
            "count=5",
            "-F",
            "name=demo",
        ],
    )
    body = json.loads(calls[0][2])
    assert body == {
        "active": True,
        "archived": False,
        "parent": None,
        "count": 5,
        "name": "demo",
    }


def test_raw_field_and_typed_field_combine(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_raw(monkeypatch, "{}")
    runner.invoke(
        app,
        ["api", "/repos", "-X", "POST", "-f", "name=demo", "-F", "count=3"],
    )
    body = json.loads(calls[0][2])
    assert body == {"name": "demo", "count": 3}


def test_typed_field_malformed_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, "{}")
    result = runner.invoke(app, ["api", "/user", "-F", "noequals"], catch_exceptions=True)
    assert result.exit_code != 0


# --- --jq -----------------------------------------------------------------


def test_jq_missing_binary_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, '{"key": "value"}')
    monkeypatch.setattr("bb.commands.api.shutil.which", lambda _name: None)
    result = runner.invoke(app, ["api", "/user", "--jq", ".key"], catch_exceptions=True)
    assert result.exit_code != 0
    assert "jq not found" in str(result.exception) or "jq not found" in result.output


def test_jq_happy_path_filters_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, '{"key": "value"}')
    monkeypatch.setattr("bb.commands.api.shutil.which", lambda _name: "/usr/bin/jq")

    def fake_run(cmd: list[str], input: str, capture_output: bool, text: bool) -> Any:  # noqa: A002
        assert cmd[0] == "/usr/bin/jq"
        assert cmd[1] == ".key"
        return subprocess.CompletedProcess(cmd, 0, stdout='"value"\n', stderr="")

    monkeypatch.setattr("bb.commands.api.subprocess.run", fake_run)
    result = runner.invoke(app, ["api", "/user", "--jq", ".key"])
    assert result.exit_code == 0
    assert result.output.strip() == '"value"'


def test_jq_nonzero_exit_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_raw(monkeypatch, '{"key": "value"}')
    monkeypatch.setattr("bb.commands.api.shutil.which", lambda _name: "/usr/bin/jq")

    def fake_run(cmd: list[str], input: str, capture_output: bool, text: bool) -> Any:  # noqa: A002
        return subprocess.CompletedProcess(cmd, 5, stdout="", stderr="jq: error: bad filter")

    monkeypatch.setattr("bb.commands.api.subprocess.run", fake_run)
    result = runner.invoke(app, ["api", "/user", "--jq", "bad("], catch_exceptions=True)
    assert result.exit_code != 0
