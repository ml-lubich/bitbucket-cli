"""
ApiClient: httpx wrapper for Bitbucket Cloud API 2.0.
Inputs: Credential, optional httpx transport (for tests).
Outputs: dict responses, ApiError on HTTP errors.
Failure modes: ApiError(status_code, message) with extracted error.message from JSON body.
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

import httpx

from bb.core.auth import Credential
from bb.core.errors import ApiError

BASE_URL = "https://api.bitbucket.org/2.0"

# backward-compat aliases
BBApiError = ApiError
APIError = ApiError


class ApiClient:
    def __init__(self, cred: Credential, transport: httpx.BaseTransport | None = None) -> None:
        self._cred = cred
        self._transport = transport

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        return _do_request(self._client(), "GET", path, params=params or None)

    def post(self, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        return _do_request(self._client(), "POST", path, json=json_body)

    def put(self, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        return _do_request(self._client(), "PUT", path, json=json_body)

    def delete(self, path: str) -> None:
        client = self._client()
        resp = client.request("DELETE", f"{BASE_URL}{path}")
        if resp.status_code == 204:
            return
        _check_error(resp)

    def paginate(self, path: str, **params: Any) -> Generator[dict[str, Any], None, None]:
        client = self._client()
        url: str | None = f"{BASE_URL}{path}"
        cur_params: dict[str, Any] | None = params or None
        while url:
            resp = client.request("GET", url, params=cur_params)
            data = _parse_resp(resp)
            yield from data.get("values", [])
            url = data.get("next")
            cur_params = None

    def raw_get(self, path: str) -> str:
        client = self._client()
        resp = client.request("GET", f"{BASE_URL}{path}")
        _check_error(resp)
        return resp.text

    def _client(self) -> httpx.Client:
        auth = _build_auth(self._cred)
        if self._transport:
            return httpx.Client(base_url=BASE_URL, auth=auth, transport=self._transport)
        return httpx.Client(base_url=BASE_URL, auth=auth)


# ── internal helpers ──────────────────────────────────────────────────────────

def _build_auth(cred: Credential) -> httpx.Auth:
    if cred.username:
        return httpx.BasicAuth(cred.username, cred.token)
    return _BearerAuth(cred.token)


class _BearerAuth(httpx.Auth):
    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


def _do_request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    resp = client.request(method, f"{BASE_URL}{path}", **kwargs)
    return _parse_resp(resp)


def _parse_resp(resp: httpx.Response) -> dict[str, Any]:
    _check_error(resp)
    if not resp.content:
        return {}
    return resp.json()


def _check_error(resp: httpx.Response) -> None:
    if not resp.is_error:
        return
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message", resp.text)
    except Exception:
        msg = resp.text
    raise ApiError(resp.status_code, msg)


def make_client() -> ApiClient:
    """Resolve credentials and return a ready ApiClient."""
    from bb.core.auth import resolve_credential
    return ApiClient(resolve_credential())


def raw_request(
    method: str,
    path: str,
    fields: dict[str, str] | None = None,
    body: str = "",
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Raw text request — used for `bb api`, pipeline logs, other text endpoints."""
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    auth = _build_auth(cred)
    headers = {"Content-Type": "application/json"} if body else None
    with _raw_client(auth, transport) as c:
        resp = c.request(method.upper(), path, params=fields, content=body or None, headers=headers)
    _check_error(resp)
    return resp.text


def _raw_client(auth: httpx.Auth, transport: httpx.BaseTransport | None) -> httpx.Client:
    if transport:
        return httpx.Client(base_url=BASE_URL, auth=auth, follow_redirects=True, transport=transport)
    return httpx.Client(base_url=BASE_URL, auth=auth, follow_redirects=True)


# BBClient alias for tests and new code
BBClient = ApiClient


def post_files(
    path: str,
    data: dict[str, str],
    files: dict[str, tuple[str, bytes]],
) -> dict[str, Any]:
    """Multipart POST for snippet file upload."""
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    auth = _build_auth(cred)
    httpx_files = {k: (v[0], v[1]) for k, v in files.items()}
    with httpx.Client(base_url=BASE_URL, auth=auth, follow_redirects=True) as c:
        resp = c.post(path, data=data, files=httpx_files)
    _check_error(resp)
    if not resp.content:
        return {}
    return resp.json()
