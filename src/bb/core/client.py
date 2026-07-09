"""
ApiClient: httpx wrapper for Bitbucket Cloud API 2.0 or Data Center REST 1.0.

Inputs: Credential, Deployment, optional httpx transport (for tests).
Outputs: dict responses, ApiError on HTTP errors.
Failure modes: ApiError(status_code, message) with extracted error.message from JSON body.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Generator
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from bb.core.auth import Credential
from bb.core.config import load_settings
from bb.core.deployment import CLOUD_API_URL, Deployment, deployment_from_base_url
from bb.core.errors import ApiError

BASE_URL = CLOUD_API_URL

# backward-compat aliases
BBApiError = ApiError
APIError = ApiError


class ApiClient:
    def __init__(
        self,
        cred: Credential,
        deployment: Deployment | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cred = cred
        self._deployment = deployment or deployment_from_base_url(
            "" if cred.host == "bitbucket.org" else f"https://{cred.host}"
        )
        self._transport = transport

    @property
    def deployment(self) -> Deployment:
        return self._deployment

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        return self._request_json("GET", path, params=params or None)

    def post(self, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request_json("POST", path, json=self._map_body(path, json_body))

    def put(self, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request_json("PUT", path, json=self._map_body(path, json_body))

    def delete(self, path: str) -> None:
        resp = self._client().request("DELETE", self._url(path))
        if resp.status_code == 204:
            return
        _check_error(resp)

    def paginate(self, path: str, **params: Any) -> Generator[dict[str, Any], None, None]:
        client = self._client()
        url: str | None = self._url(path)
        cur_params: dict[str, Any] | None = params or None
        while url:
            resp = client.request("GET", url, params=cur_params)
            raw = _parse_resp(resp)
            data = self._normalize(path, raw)
            yield from data.get("values", [])
            next_url = data.get("next")
            if next_url:
                url = str(next_url)
                cur_params = None
                continue
            if self._deployment.is_datacenter and raw.get("nextPageStart") is not None:
                url = self._url(path)
                cur_params = dict(params)
                cur_params["start"] = raw["nextPageStart"]
                continue
            url = None

    def raw_get(self, path: str) -> str:
        resp = self._client().request("GET", self._url(path))
        _check_error(resp)
        return resp.text

    def _client(self) -> httpx.Client:
        auth = _build_auth(self._cred)
        if self._transport:
            return httpx.Client(
                base_url=self._deployment.api_url,
                auth=auth,
                transport=self._transport,
            )
        return httpx.Client(base_url=self._deployment.api_url, auth=auth)

    def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        resp = self._client().request(method, self._url(path), **kwargs)
        return self._normalize(path, _parse_resp(resp))

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        mapped = self._map_path(path)
        return f"{self._deployment.api_url}{mapped}"

    def _map_path(self, path: str) -> str:
        if self._deployment.is_cloud:
            return path
        return _map_datacenter_path(path)

    def _map_body(self, path: str, body: dict[str, Any] | None) -> dict[str, Any] | None:
        if not body or self._deployment.is_cloud:
            return body
        return _map_datacenter_body(path, body)

    def _normalize(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if self._deployment.is_cloud:
            return data
        return _normalize_datacenter_response(path, data, self._deployment.web_url)


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
    return cast(dict[str, Any], resp.json())


def _check_error(resp: httpx.Response) -> None:
    if not resp.is_error:
        return
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message") or body.get("message") or resp.text
    except Exception:
        msg = resp.text
    method = ""
    path = ""
    try:
        method = resp.request.method
        parsed = urlparse(str(resp.request.url))
        path = parsed.path
    except RuntimeError:
        pass
    raise ApiError(resp.status_code, msg, method=method, path=path, hint=_api_hint(resp.status_code))


def _api_hint(status_code: int) -> str:
    hints = {
        401: "Token is missing, expired, revoked, or uses the wrong auth type.",
        403: "Token lacks permission for this resource or the repository is restricted.",
        404: "Check the project/workspace, repository slug, and whether the feature is enabled.",
        409: "The requested change conflicts with the current repository state.",
    }
    if 500 <= status_code <= 599:
        return "Bitbucket returned a server error; retry or check the Bitbucket status page."
    return hints.get(status_code, "")


def make_client(base_url: str = "") -> ApiClient:
    """Resolve credentials and return a ready ApiClient."""
    from bb.core.auth import resolve_credential
    settings = load_settings()
    deployment = deployment_from_base_url(base_url or settings.base_url)
    return ApiClient(resolve_credential(host=deployment.host), deployment=deployment)


def raw_request(
    method: str,
    path: str,
    fields: dict[str, str] | None = None,
    body: str = "",
    base_url: str = "",
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Raw text request — used for `bb api`, pipeline logs, other text endpoints."""
    from bb.core.auth import resolve_credential
    deployment = deployment_from_base_url(base_url or load_settings().base_url)
    cred = resolve_credential(host=deployment.host)
    auth = _build_auth(cred)
    mapped_path = path if deployment.is_cloud else _map_datacenter_path(path)
    url = mapped_path if mapped_path.startswith(("http://", "https://")) else f"{deployment.api_url}{mapped_path}"
    headers = {"Content-Type": "application/json"} if body else None
    with _raw_client(auth, deployment, transport) as c:
        resp = c.request(method.upper(), url, params=fields, content=body or None, headers=headers)
    _check_error(resp)
    return resp.text


def _raw_client(
    auth: httpx.Auth,
    deployment: Deployment | None = None,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    deployment = deployment or deployment_from_base_url()
    if transport:
        return httpx.Client(
            base_url=deployment.api_url,
            auth=auth,
            follow_redirects=True,
            transport=transport,
        )
    return httpx.Client(base_url=deployment.api_url, auth=auth, follow_redirects=True)


# BBClient alias for tests and new code
BBClient = ApiClient


def post_files(
    path: str,
    data: dict[str, str],
    files: dict[str, tuple[str, bytes]],
) -> dict[str, Any]:
    """Multipart POST for snippet file upload."""
    from bb.core.auth import resolve_credential
    deployment = deployment_from_base_url(load_settings().base_url)
    cred = resolve_credential(host=deployment.host)
    auth = _build_auth(cred)
    httpx_files = {k: (v[0], v[1]) for k, v in files.items()}
    mapped_path = path if deployment.is_cloud else _map_datacenter_path(path)
    url = mapped_path if mapped_path.startswith(("http://", "https://")) else f"{deployment.api_url}{mapped_path}"
    with httpx.Client(base_url=deployment.api_url, auth=auth, follow_redirects=True) as c:
        resp = c.post(url, data=data, files=httpx_files)
    _check_error(resp)
    if not resp.content:
        return {}
    return cast(dict[str, Any], resp.json())


_REPO_PATH_RE = re.compile(r"^/repositories/([^/]+)/([^/]+)/?$")
_REPO_LIST_RE = re.compile(r"^/repositories/([^/]+)/?$")
_PR_BASE_RE = re.compile(r"^/repositories/([^/]+)/([^/]+)/pullrequests/?$")
_PR_ITEM_RE = re.compile(r"^/repositories/([^/]+)/([^/]+)/pullrequests/([^/]+)(/.*)?$")
_BRANCH_BASE_RE = re.compile(r"^/repositories/([^/]+)/([^/]+)/refs/branches/?$")
_BRANCH_ITEM_RE = re.compile(r"^/repositories/([^/]+)/([^/]+)/refs/branches/([^/]+)/?$")
_WORKSPACE_ITEM_RE = re.compile(r"^/workspaces/([^/]+)/?$")
_PROJECTS_RE = re.compile(r"^/workspaces/([^/]+)/projects/?$")
_PROJECT_ITEM_RE = re.compile(r"^/workspaces/([^/]+)/projects/([^/]+)/?$")


def _map_datacenter_path(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    path = _strip_dc_api_prefix(path)
    if path == "/user":
        return "/projects"
    if path == "/workspaces":
        return "/projects"
    m = _WORKSPACE_ITEM_RE.match(path)
    if m:
        return f"/projects/{m.group(1)}"
    m = _PROJECTS_RE.match(path)
    if m:
        return "/projects"
    m = _PROJECT_ITEM_RE.match(path)
    if m:
        return f"/projects/{m.group(2)}"
    m = _REPO_PATH_RE.match(path)
    if m:
        return f"/projects/{m.group(1)}/repos/{m.group(2)}"
    m = _REPO_LIST_RE.match(path)
    if m:
        return f"/projects/{m.group(1)}/repos"
    m = _PR_BASE_RE.match(path)
    if m:
        return f"/projects/{m.group(1)}/repos/{m.group(2)}/pull-requests"
    m = _PR_ITEM_RE.match(path)
    if m:
        suffix = m.group(4) or ""
        return f"/projects/{m.group(1)}/repos/{m.group(2)}/pull-requests/{m.group(3)}{suffix}"
    m = _BRANCH_BASE_RE.match(path)
    if m:
        return f"/projects/{m.group(1)}/repos/{m.group(2)}/branches"
    m = _BRANCH_ITEM_RE.match(path)
    if m:
        return f"/projects/{m.group(1)}/repos/{m.group(2)}/branches?filterText={m.group(3)}"
    return path


def _strip_dc_api_prefix(path: str) -> str:
    for prefix in ("/rest/api/1.0", "/rest/api/latest"):
        if path == prefix:
            return "/"
        if path.startswith(f"{prefix}/"):
            return path[len(prefix):]
    return path


def _map_datacenter_body(path: str, body: dict[str, Any]) -> dict[str, Any]:
    if _PROJECTS_RE.match(path):
        project_body = dict(body)
        if "is_private" in project_body:
            project_body["public"] = not bool(project_body.pop("is_private"))
        return project_body
    m = _PR_BASE_RE.match(path)
    if not m:
        return body
    project, repo = m.group(1), m.group(2)
    src = ((body.get("source") or {}).get("branch") or {}).get("name", "")
    dst = ((body.get("destination") or {}).get("branch") or {}).get("name", "")
    pr_body: dict[str, Any] = {
        "title": body.get("title", ""),
        "fromRef": _dc_ref(project, repo, str(src)),
        "toRef": _dc_ref(project, repo, str(dst)),
    }
    if body.get("description"):
        pr_body["description"] = body["description"]
    return pr_body


def _dc_ref(project: str, repo: str, branch: str) -> dict[str, Any]:
    ref_id = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    return {
        "id": ref_id,
        "repository": {
            "slug": repo,
            "project": {"key": project},
        },
    }


def _normalize_datacenter_response(path: str, data: dict[str, Any], web_url: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return data
    if _REPO_LIST_RE.match(path):
        return _normalize_values(data, lambda item: _normalize_dc_repo(item, web_url))
    if _REPO_PATH_RE.match(path):
        return _normalize_dc_repo(data, web_url)
    if _PR_BASE_RE.match(path):
        if isinstance(data.get("values"), list):
            return _normalize_values(data, lambda item: _normalize_dc_pr(item, web_url))
        return _normalize_dc_pr(data, web_url)
    if _PR_ITEM_RE.match(path):
        return _normalize_dc_pr(data, web_url)
    if _BRANCH_BASE_RE.match(path):
        return _normalize_values(data, _normalize_dc_branch)
    if _PROJECTS_RE.match(path) or path in {"/workspaces", "/user"}:
        return _normalize_values(data, lambda item: _normalize_dc_project(item, web_url))
    if _PROJECT_ITEM_RE.match(path) or _WORKSPACE_ITEM_RE.match(path):
        return _normalize_dc_project(data, web_url)
    return data


def _normalize_values(
    data: dict[str, Any],
    mapper: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    result = dict(data)
    if isinstance(result.get("values"), list):
        result["values"] = [mapper(item) for item in result["values"]]
    return result


def _normalize_dc_repo(repo: dict[str, Any], web_url: str) -> dict[str, Any]:
    project = repo.get("project") or {}
    project_key = str(project.get("key", ""))
    slug = str(repo.get("slug") or repo.get("name") or "")
    html_url = _first_link(repo, "self") or f"{web_url}/projects/{project_key}/repos/{slug}"
    clone_links = []
    for link in (repo.get("links") or {}).get("clone", []):
        name = str(link.get("name", ""))
        clone_links.append({"name": "https" if name == "http" else name, "href": link.get("href", "")})
    result = dict(repo)
    result.update(
        {
            "full_name": f"{project_key}/{slug}" if project_key else slug,
            "is_private": not bool(repo.get("public", False)),
            "updated_on": str(repo.get("updatedDate", "")),
            "links": {
                **(repo.get("links") or {}),
                "html": {"href": html_url},
                "clone": clone_links,
            },
        }
    )
    if "mainbranch" not in result:
        result["mainbranch"] = {"name": repo.get("defaultBranch", "main")}
    return result


def _normalize_dc_project(project: dict[str, Any], web_url: str) -> dict[str, Any]:
    key = str(project.get("key", ""))
    result = dict(project)
    # Cloud workspaces expose `slug`; DC projects expose `key`. Map key→slug so
    # `bb workspace list/view` and Cloud-shaped callers can use one identifier.
    result["slug"] = str(project.get("slug") or key)
    result["is_private"] = project.get("public") is False
    result["links"] = {
        **(project.get("links") or {}),
        "html": {"href": _first_link(project, "self") or f"{web_url}/projects/{key}"},
    }
    return result


def _normalize_dc_pr(pr: dict[str, Any], web_url: str) -> dict[str, Any]:
    from_ref = pr.get("fromRef") or {}
    to_ref = pr.get("toRef") or {}
    repo = from_ref.get("repository") or to_ref.get("repository") or {}
    project = repo.get("project") or {}
    project_key = str(project.get("key", ""))
    slug = str(repo.get("slug", ""))
    pr_id = pr.get("id", "")
    author_user = (pr.get("author") or {}).get("user") or {}
    result = dict(pr)
    result.update(
        {
            "source": {"branch": {"name": from_ref.get("displayId") or _ref_name(from_ref)}},
            "destination": {"branch": {"name": to_ref.get("displayId") or _ref_name(to_ref)}},
            "author": {"display_name": author_user.get("displayName", "")},
            "description": pr.get("description", ""),
            "created_on": pr.get("createdDate", ""),
            "links": {
                **(pr.get("links") or {}),
                "html": {
                    "href": _first_link(pr, "self")
                    or f"{web_url}/projects/{project_key}/repos/{slug}/pull-requests/{pr_id}"
                },
            },
        }
    )
    return result


def _normalize_dc_branch(branch: dict[str, Any]) -> dict[str, Any]:
    result = dict(branch)
    if "target" not in result:
        result["target"] = {"hash": branch.get("latestCommit", "")}
    return result


def _first_link(data: dict[str, Any], key: str) -> str:
    link = (data.get("links") or {}).get(key)
    if isinstance(link, list) and link:
        return str(link[0].get("href", ""))
    if isinstance(link, dict):
        return str(link.get("href", ""))
    return ""


def _ref_name(ref: dict[str, Any]) -> str:
    ref_id = str(ref.get("id", ""))
    return ref_id.removeprefix("refs/heads/")
