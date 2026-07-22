"""Tests for the read-only MCP server (bb mcp serve)."""
from __future__ import annotations

import io
import json
from typing import Any

from bb.commands import mcp


class FakeClient:
    """Read-only stand-in. Deliberately has NO post/put/delete — if the server
    ever tries to mutate, the test crashes with AttributeError."""

    def __init__(self) -> None:
        self.gets: list[str] = []

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        self.gets.append(path)
        if path == "/user":
            return {"display_name": "Misha", "uuid": "{abc}"}
        return {"path": path, "params": params}

    def paginate(self, path: str, **params: Any):
        for i in range(3):
            yield {"n": i, "path": path, "params": params}


def factory() -> FakeClient:
    return FakeClient()


def _text(resp: dict[str, Any]) -> Any:
    return json.loads(resp["result"]["content"][0]["text"])


def test_initialize_echoes_protocol_and_server_info() -> None:
    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18"}},
        factory,
    )
    assert r is not None
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert r["result"]["serverInfo"]["name"] == "bb"
    assert "tools" in r["result"]["capabilities"]


def test_initialize_defaults_protocol_when_absent() -> None:
    r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, factory)
    assert r is not None
    assert r["result"]["protocolVersion"] == mcp.PROTOCOL_VERSION


def test_notification_produces_no_response() -> None:
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, factory) is None


def test_ping() -> None:
    r = mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "ping"}, factory)
    assert r == {"jsonrpc": "2.0", "id": 9, "result": {}}


def test_tools_list_is_readonly_and_hides_internals() -> None:
    r = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, factory)
    assert r is not None
    tools = r["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"whoami", "api_get", "repo_list", "repo_view", "pr_list", "pr_view",
            "issue_list", "pipeline_list"} <= names
    for t in tools:
        assert "_fn" not in t  # internal handler must not leak
        assert "inputSchema" in t


def test_call_whoami() -> None:
    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "whoami", "arguments": {}}},
        factory,
    )
    assert r is not None
    assert r["result"]["isError"] is False
    assert _text(r)["display_name"] == "Misha"


def test_call_pr_list_limits_pagination() -> None:
    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "pr_list", "arguments": {"workspace": "w", "repo": "r", "limit": 2}}},
        factory,
    )
    assert r is not None
    assert len(_text(r)) == 2


def test_call_api_get_passes_path_through() -> None:
    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "api_get", "arguments": {"path": "/repositories/w"}}},
        factory,
    )
    assert r is not None
    assert _text(r)["path"] == "/repositories/w"


def test_missing_required_arg_is_tool_error() -> None:
    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "repo_view", "arguments": {"workspace": "w"}}},
        factory,
    )
    assert r is not None
    assert r["result"]["isError"] is True
    assert "missing required argument" in r["result"]["content"][0]["text"]


def test_api_error_becomes_tool_error_not_crash() -> None:
    def boom() -> FakeClient:
        raise RuntimeError("401 unauthorized")

    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "whoami", "arguments": {}}},
        boom,
    )
    assert r is not None
    assert r["result"]["isError"] is True
    assert "401 unauthorized" in r["result"]["content"][0]["text"]


def test_unknown_tool() -> None:
    r = mcp.handle(
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
         "params": {"name": "nope", "arguments": {}}},
        factory,
    )
    assert r is not None
    assert r["error"]["code"] == -32602


def test_unknown_method() -> None:
    r = mcp.handle({"jsonrpc": "2.0", "id": 10, "method": "bogus"}, factory)
    assert r is not None
    assert r["error"]["code"] == -32601


def test_serve_stdio_roundtrip() -> None:
    inp = io.StringIO(
        "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            "",  # blank line must be skipped
            "{ not json",  # garbage must be skipped
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ]) + "\n"
    )
    out = io.StringIO()
    mcp._serve_stdio(read=inp, write=out, client_factory=factory)
    lines = [json.loads(x) for x in out.getvalue().splitlines() if x.strip()]
    # initialize + tools/list produce output; notification/blank/garbage do not
    assert len(lines) == 2
    assert lines[0]["result"]["serverInfo"]["name"] == "bb"
    assert {t["name"] for t in lines[1]["result"]["tools"]}
