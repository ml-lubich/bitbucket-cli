"""
mcp.py — Read-only Model Context Protocol server over stdio (JSON-RPC 2.0).

Exposes bb's read paths as MCP tools so coding agents (Claude, Codex, …) can
query Bitbucket Cloud or Data Center directly. Read-only by construction: every
tool calls `client.get`/`client.paginate` only — no post/put/delete is reachable.
Because ApiClient maps Cloud-style paths to Data Center `/rest/api/1.0`
automatically, the same tools work against on-prem hosts with no extra code.

Inputs : newline-delimited JSON-RPC messages on stdin.
Outputs: JSON-RPC responses on stdout (notifications produce no response).
Failure: tool/API errors are returned as MCP tool errors, not crashes.

ponytail: hand-rolls the MCP stdio subset (initialize + tools/*) to avoid the
heavy `mcp` SDK dependency. Swap in the official SDK if we ever need resources,
prompts, or streaming.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from typing import Any, TextIO

import typer

from bb import __version__
from bb.core.client import ApiClient, make_client

app = typer.Typer(help="Read-only MCP server for coding agents", no_args_is_help=True)

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "bb", "version": __version__}

ClientFactory = Callable[[], ApiClient]

# --- read-only tool implementations -----------------------------------------


def _limited(client: ApiClient, path: str, limit: int, **params: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in client.paginate(path, **params):
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _whoami(client: ApiClient, args: dict[str, Any]) -> Any:
    return client.get("/user")


def _api_get(client: ApiClient, args: dict[str, Any]) -> Any:
    return client.get(args["path"])


def _repo_list(client: ApiClient, args: dict[str, Any]) -> Any:
    return _limited(client, f"/repositories/{args['workspace']}", int(args.get("limit", 25)))


def _repo_view(client: ApiClient, args: dict[str, Any]) -> Any:
    return client.get(f"/repositories/{args['workspace']}/{args['repo']}")


def _pr_list(client: ApiClient, args: dict[str, Any]) -> Any:
    path = f"/repositories/{args['workspace']}/{args['repo']}/pullrequests"
    return _limited(client, path, int(args.get("limit", 25)), state=args.get("state", "OPEN"))


def _pr_view(client: ApiClient, args: dict[str, Any]) -> Any:
    return client.get(
        f"/repositories/{args['workspace']}/{args['repo']}/pullrequests/{args['id']}"
    )


def _issue_list(client: ApiClient, args: dict[str, Any]) -> Any:
    path = f"/repositories/{args['workspace']}/{args['repo']}/issues"
    return _limited(client, path, int(args.get("limit", 25)))


def _pipeline_list(client: ApiClient, args: dict[str, Any]) -> Any:
    path = f"/repositories/{args['workspace']}/{args['repo']}/pipelines/"
    return _limited(client, path, int(args.get("limit", 25)))


_WS = {"workspace": {"type": "string", "description": "Workspace slug (Cloud) or project key (Data Center)"}}
_REPO = {**_WS, "repo": {"type": "string", "description": "Repository slug"}}
_LIMIT = {"limit": {"type": "integer", "description": "Max items to return", "default": 25}}


def _schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


TOOLS: list[dict[str, Any]] = [
    {"name": "whoami", "description": "The authenticated Bitbucket user.",
     "inputSchema": _schema({}, []), "_fn": _whoami},
    {"name": "api_get", "description": "Read-only GET on any Bitbucket API path, e.g. /user or /repositories/{ws}.",
     "inputSchema": _schema({"path": {"type": "string", "description": "API path starting with /"}}, ["path"]),
     "_fn": _api_get},
    {"name": "repo_list", "description": "List repositories in a workspace/project.",
     "inputSchema": _schema({**_WS, **_LIMIT}, ["workspace"]), "_fn": _repo_list},
    {"name": "repo_view", "description": "Details of a single repository.",
     "inputSchema": _schema(_REPO, ["workspace", "repo"]), "_fn": _repo_view},
    {"name": "pr_list", "description": "List pull requests in a repository (default state OPEN).",
     "inputSchema": _schema({**_REPO, "state": {"type": "string", "description": "OPEN, MERGED, DECLINED, …"}, **_LIMIT}, ["workspace", "repo"]),
     "_fn": _pr_list},
    {"name": "pr_view", "description": "Details of a single pull request.",
     "inputSchema": _schema({**_REPO, "id": {"type": "integer", "description": "Pull request ID"}}, ["workspace", "repo", "id"]),
     "_fn": _pr_view},
    {"name": "issue_list", "description": "List issues in a repository (Bitbucket Cloud).",
     "inputSchema": _schema({**_REPO, **_LIMIT}, ["workspace", "repo"]), "_fn": _issue_list},
    {"name": "pipeline_list", "description": "List pipelines in a repository.",
     "inputSchema": _schema({**_REPO, **_LIMIT}, ["workspace", "repo"]), "_fn": _pipeline_list},
]
_TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


# --- JSON-RPC plumbing ------------------------------------------------------


def _result(mid: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _tool_error(mid: Any, message: str) -> dict[str, Any]:
    return _result(mid, {"content": [{"type": "text", "text": message}], "isError": True})


def _public(tool: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in tool.items() if not k.startswith("_")}


def _call_tool(mid: Any, params: dict[str, Any], client_factory: ClientFactory) -> dict[str, Any]:
    spec = _TOOLS_BY_NAME.get(params.get("name", ""))
    if spec is None:
        return _error(mid, -32602, f"unknown tool: {params.get('name')!r}")
    args = params.get("arguments") or {}
    try:
        data = spec["_fn"](client_factory(), args)
    except KeyError as exc:  # a required argument was not provided
        return _tool_error(mid, f"missing required argument: {exc}")
    except Exception as exc:  # surface auth/API errors to the agent, don't crash the server
        return _tool_error(mid, f"{type(exc).__name__}: {exc}")
    return _result(mid, {"content": [{"type": "text", "text": json.dumps(data, indent=2, default=str)}],
                         "isError": False})


def handle(msg: dict[str, Any], client_factory: ClientFactory = make_client) -> dict[str, Any] | None:
    """Process one JSON-RPC message. Returns a response, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return _result(mid, {"protocolVersion": requested,
                             "capabilities": {"tools": {}},
                             "serverInfo": SERVER_INFO})
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": [_public(t) for t in TOOLS]})
    if method == "tools/call":
        return _call_tool(mid, msg.get("params") or {}, client_factory)
    if mid is None:  # any other notification (e.g. notifications/initialized)
        return None
    return _error(mid, -32601, f"method not found: {method}")


def _serve_stdio(
    read: Iterable[str] | TextIO = sys.stdin,
    write: TextIO = sys.stdout,
    client_factory: ClientFactory = make_client,
) -> None:
    for line in read:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg, client_factory)
        if resp is not None:
            write.write(json.dumps(resp) + "\n")
            write.flush()


@app.command("serve")
def serve() -> None:
    """Run a read-only MCP server over stdio (JSON-RPC 2.0) for coding agents."""
    _serve_stdio()
