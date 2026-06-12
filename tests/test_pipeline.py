"""Tests for bb pipeline commands."""
from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest
from typer.testing import CliRunner

from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.core.context import RepoContext
from bb.main import app

runner = CliRunner()
_CRED = Credential(host="bitbucket.org", token="x", auth_type="bearer", username="")
_REPO = RepoContext(workspace="ws", slug="repo")


def _make_transport(handler: Callable) -> httpx.MockTransport:
    return httpx.MockTransport(handler)  # type: ignore[arg-type]


def _mock_client(responses: list[httpx.Response]) -> ApiClient:
    idx = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal idx
        r = responses[idx]
        idx += 1
        return r

    return ApiClient(_CRED, transport=_make_transport(handler))


def _patch(monkeypatch: pytest.MonkeyPatch, responses: list[httpx.Response]) -> ApiClient:
    client = _mock_client(responses)
    monkeypatch.setattr("bb.commands.pipeline.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.pipeline.current_repo", lambda *_a, **_kw: _REPO)
    return client


def test_pipeline_list_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    result = runner.invoke(app, ["pipeline", "list"])
    assert result.exit_code == 0


def test_pipeline_list_shows_build(monkeypatch: pytest.MonkeyPatch) -> None:
    pipe = {
        "build_number": 42, "uuid": "{abc}", "created_on": "2026-01-01T00:00:00Z",
        "state": {"name": "COMPLETED", "result": {"name": "SUCCESSFUL"}},
        "target": {"ref_name": "main"},
    }
    _patch(monkeypatch, [httpx.Response(200, json={"values": [pipe]})])
    result = runner.invoke(app, ["pipeline", "list"])
    assert "42" in result.output


def test_pipeline_run_posts_ref_name_from_current_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(201, json={"build_number": 1, "uuid": "{x}"})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.pipeline.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.pipeline.current_repo", lambda *_a, **_kw: _REPO)
    monkeypatch.setattr("bb.commands.pipeline.current_branch", lambda: "feature/abc")
    runner.invoke(app, ["pipeline", "run"])
    body = json.loads(captured[0].content)
    assert body["target"]["ref_name"] == "feature/abc"


def test_pipeline_run_explicit_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(201, json={"build_number": 2, "uuid": "{y}"})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.pipeline.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.pipeline.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["pipeline", "run", "--branch", "main"])
    body = json.loads(captured[0].content)
    assert body["target"]["ref_name"] == "main"


def test_pipeline_view_normalizes_uuid_without_braces(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        pipe = {
            "build_number": 7, "uuid": "{abc-123}", "created_on": "2026-01-01T00:00:00Z",
            "state": {"name": "COMPLETED"}, "target": {"ref_name": "main"},
        }
        return httpx.Response(200, json=pipe)

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.pipeline.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.pipeline.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["pipeline", "view", "abc-123"])
    assert "{abc-123}" in captured[0].url.path


def test_pipeline_view_normalizes_uuid_with_braces(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        pipe = {
            "build_number": 8, "state": {"name": "RUNNING"}, "target": {"ref_name": "dev"},
            "uuid": "{xyz}", "created_on": "2026-01-01",
        }
        return httpx.Response(200, json=pipe)

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.pipeline.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.pipeline.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["pipeline", "view", "{xyz}"])
    assert "{xyz}" in captured[0].url.path


def test_pipeline_steps_lists_names(monkeypatch: pytest.MonkeyPatch) -> None:
    steps = [{"name": "build", "state": {"name": "COMPLETED"}, "uuid": "{s1}"}]
    _patch(monkeypatch, [httpx.Response(200, json={"values": steps})])
    result = runner.invoke(app, ["pipeline", "steps", "abc-123"])
    assert "build" in result.output


def test_pipeline_stop_hits_stop_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json={})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.pipeline.make_client", lambda: client)
    monkeypatch.setattr("bb.commands.pipeline.current_repo", lambda *_a, **_kw: _REPO)
    runner.invoke(app, ["pipeline", "stop", "abc-123"])
    assert "stopPipeline" in captured[0].url.path


def test_pipeline_logs_single_step(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_paths: list[str] = []

    def mock_raw(method: str, path: str, fields=None) -> str:
        captured_paths.append(path)
        return "log output"

    _patch(monkeypatch, [])
    monkeypatch.setattr("bb.commands.pipeline.raw_request", mock_raw)
    result = runner.invoke(app, ["pipeline", "logs", "abc-123", "--step", "step-uuid-1"])
    assert "log output" in result.output


def test_pipeline_logs_all_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    steps = [
        {"name": "build", "state": {"name": "COMPLETED"}, "uuid": "{s1}"},
        {"name": "test", "state": {"name": "COMPLETED"}, "uuid": "{s2}"},
    ]
    log_calls: list[str] = []

    def mock_raw(method: str, path: str, fields=None) -> str:
        log_calls.append(path)
        return "step log"

    _patch(monkeypatch, [httpx.Response(200, json={"values": steps})])
    monkeypatch.setattr("bb.commands.pipeline.raw_request", mock_raw)
    runner.invoke(app, ["pipeline", "logs", "abc-123"])
    assert len(log_calls) == 2
