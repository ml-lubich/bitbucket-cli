"""
deployment.py — Bitbucket Cloud/Data Center endpoint resolution.

Inputs : configured base URL, remote URLs.
Outputs: Deployment with web/API roots and provider kind.
Failure: none; unknown hosts are treated as Bitbucket Data Center.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

CLOUD_HOST = "bitbucket.org"
CLOUD_WEB_URL = "https://bitbucket.org"
CLOUD_API_URL = "https://api.bitbucket.org/2.0"
DATA_CENTER_API_PATH = "/rest/api/1.0"


@dataclass(frozen=True)
class Deployment:
    kind: str
    web_url: str
    api_url: str
    host: str

    @property
    def is_cloud(self) -> bool:
        return self.kind == "cloud"

    @property
    def is_datacenter(self) -> bool:
        return self.kind == "datacenter"


def default_deployment() -> Deployment:
    return Deployment(
        kind="cloud",
        web_url=CLOUD_WEB_URL,
        api_url=CLOUD_API_URL,
        host=CLOUD_HOST,
    )


def deployment_from_base_url(value: str = "") -> Deployment:
    base_url = normalize_base_url(value)
    parsed = urlparse(base_url)
    host = (parsed.hostname or CLOUD_HOST).lower()
    if host in {CLOUD_HOST, "api.bitbucket.org"}:
        return default_deployment()
    return Deployment(
        kind="datacenter",
        web_url=base_url,
        api_url=f"{base_url}{DATA_CENTER_API_PATH}",
        host=parsed.netloc.lower(),
    )


def normalize_base_url(value: str = "") -> str:
    raw = (value or "").strip()
    if not raw:
        return CLOUD_WEB_URL
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    path = _normalize_web_path(parsed.path)
    if (parsed.hostname or "").lower() in {CLOUD_HOST, "api.bitbucket.org"}:
        return CLOUD_WEB_URL
    return urlunparse((scheme, netloc, path, "", "", "")).rstrip("/")


def base_url_from_remote(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        path = _normalize_web_path(parsed.path)
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")
    ssh = re.match(r"(?:ssh://)?git@(?P<host>[^/:]+)(?::(?P<port>\d+))?", url)
    if ssh:
        host = ssh.group("host")
        if host == CLOUD_HOST:
            return CLOUD_WEB_URL
        netloc = host
        if ssh.group("port"):
            netloc = f"{host}:{ssh.group('port')}"
        return f"https://{netloc}"
    return ""


def _normalize_web_path(path: str) -> str:
    cleaned = path.rstrip("/")
    if not cleaned:
        return ""
    rest_index = cleaned.find("/rest/api/")
    if rest_index >= 0:
        return cleaned[:rest_index]
    first_segment = cleaned.split("/", 2)[1] if cleaned.startswith("/") else cleaned.split("/", 1)[0]
    # These are Bitbucket application routes, not context paths.
    if first_segment in {
        "plugins",
        "projects",
        "repos",
        "scm",
        "users",
        "dashboard",
        "browse",
    }:
        return ""
    return cleaned
