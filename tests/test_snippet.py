"""Tests for bb snippet commands."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx
import pytest
from typer.testing import CliRunner

from bb.core.auth import Credential
from bb.core.client import ApiClient
from bb.cli import app

runner = CliRunner()
_CRED = Credential(host="bitbucket.org", token="x", auth_type="bearer", username="")


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
    monkeypatch.setattr("bb.commands.snippet.make_client", lambda: client)
    return client


def test_snippet_list_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(200, json={"values": []})])
    result = runner.invoke(app, ["snippet", "list"])
    assert result.exit_code == 0


def test_snippet_list_shows_title(monkeypatch: pytest.MonkeyPatch) -> None:
    snip = {"id": "abc", "title": "My Snippet", "is_private": True, "owner": {"display_name": "Alice"}}
    _patch(monkeypatch, [httpx.Response(200, json={"values": [snip]})])
    result = runner.invoke(app, ["snippet", "list"])
    assert "My Snippet" in result.output


def test_snippet_view_shows_title(monkeypatch: pytest.MonkeyPatch) -> None:
    snip = {
        "title": "Snip", "is_private": True, "files": {"hello.txt": {}},
        "owner": {"display_name": "Bob"},
    }
    _patch(monkeypatch, [httpx.Response(200, json=snip)])
    result = runner.invoke(app, ["snippet", "view", "ws", "abc"])
    assert "Snip" in result.output


def test_snippet_view_raw_file(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def mock_raw(method: str, path: str, fields=None) -> str:
        captured.append(path)
        return "raw content"

    _patch(monkeypatch, [])
    monkeypatch.setattr("bb.commands.snippet.raw_request", mock_raw)
    result = runner.invoke(app, ["snippet", "view", "ws", "abc", "--raw", "--file", "hello.txt"])
    assert "raw content" in result.output


def test_snippet_create_reads_real_file_and_passes_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fpath = tmp_path / "data.txt"
    fpath.write_bytes(b"hello world")
    captured_calls: list[dict] = []

    def mock_post_files(path: str, data: dict, files: dict) -> dict:
        captured_calls.append({"data": data, "files": files})
        return {"id": "snip123"}

    monkeypatch.setattr("bb.commands.snippet.post_files", mock_post_files)
    runner.invoke(app, ["snippet", "create", "--title", "T", "--file", str(fpath)])
    assert captured_calls[0]["files"]["file"][1] == b"hello world"


def test_snippet_create_prints_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fpath = tmp_path / "f.txt"
    fpath.write_bytes(b"x")
    monkeypatch.setattr("bb.commands.snippet.post_files", lambda *a, **kw: {"id": "XY99"})
    result = runner.invoke(app, ["snippet", "create", "--title", "T", "--file", str(fpath)])
    assert "XY99" in result.output


def test_snippet_create_missing_file_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bb.commands.snippet.post_files", lambda *a, **kw: {"id": "x"})
    result = runner.invoke(app, ["snippet", "create", "--title", "T", "--file", "/no/such/file.txt"])
    assert result.exit_code != 0


def test_snippet_edit_puts_title(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json={})

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.snippet.make_client", lambda: client)
    runner.invoke(app, ["snippet", "edit", "ws", "abc", "--title", "New Title"])
    import json
    body = json.loads(captured[0].content)
    assert body["title"] == "New Title"


def test_snippet_edit_no_title_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [])
    result = runner.invoke(app, ["snippet", "edit", "ws", "abc"])
    assert result.exit_code != 0


def test_snippet_delete_with_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(204)

    client = ApiClient(_CRED, transport=_make_transport(handler))
    monkeypatch.setattr("bb.commands.snippet.make_client", lambda: client)
    result = runner.invoke(app, ["snippet", "delete", "ws", "abc", "--yes"])
    assert result.exit_code == 0


def test_snippet_delete_prompts_without_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [httpx.Response(204)])
    # no input → abort → non-zero
    result = runner.invoke(app, ["snippet", "delete", "ws", "abc"])
    assert result.exit_code != 0
