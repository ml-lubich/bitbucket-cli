"""
auth.py — Credential resolution + persistent token store.

Inputs : env BB_TOKEN > BITBUCKET_TOKEN > BITBUCKET_AUTH_TOKEN > .env file
         (same three keys, simple KEY=VALUE/KEY="VALUE" lines) > hosts.toml.
Outputs: Credential / Credentials dataclasses; hosts.toml chmod 0600.
Failure: AuthError when no credential found. Tokens never logged.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from platformdirs import user_config_dir

from bb.core.errors import AuthError

HOST = "bitbucket.org"
TOKEN_VARS = ("BB_TOKEN", "BITBUCKET_TOKEN", "BITBUCKET_AUTH_TOKEN")


# ── New API (used by ApiClient, commands) ─────────────────────────────────────

@dataclass(frozen=True)
class Credential:
    token: str
    host: str = HOST
    auth_type: str = "bearer"  # "bearer" | "basic"
    username: str = ""
    source: str = "hosts"  # "env:<NAME>" | "dotenv:<NAME>" | "hosts"


# ── Legacy API (test_auth.py, test_client.py compat) ─────────────────────────

@dataclass(frozen=True)
class Credentials:
    token: str
    username: str = ""


# ── Public new API ────────────────────────────────────────────────────────────

def masked(token: str) -> str:
    return token[:4] + "****"


def resolve_credential(host: str = HOST) -> Credential:
    cred = _env_token()
    if cred:
        return cred
    cred = _denv_token()
    if cred:
        return cred
    file_cred = _cred_from_file(host)
    if file_cred:
        return file_cred
    raise AuthError("not authenticated — run `bb auth login` or set BB_TOKEN")


def stored_credential(host: str = HOST) -> Credential:
    cred = _cred_from_file(host)
    if not cred:
        raise AuthError(f"no stored credential for {host!r}")
    return cred


def save_credential(cred: Credential) -> Path:
    doc = _read_hosts()
    entry = tomlkit.table()
    entry.add("token", cred.token)
    entry.add("auth_type", cred.auth_type)
    if cred.username:
        entry.add("username", cred.username)
    doc[cred.host] = entry  # type: ignore[index]
    _write_hosts(doc)
    return _hosts_path()


def delete_credential(host: str = HOST) -> bool:
    doc = _read_hosts()
    if _entry_for_host(doc, host) is None:
        return False
    _del_host_entry(doc, host)
    path = _hosts_path()
    if not doc.body or not any(isinstance(item[1], tomlkit.items.Table) for item in doc.body):
        if path.exists():
            path.unlink()
    else:
        _write_hosts(doc)
    return True


def _del_host_entry(doc: tomlkit.TOMLDocument, host: str) -> None:
    # Quoted key format — try direct deletion first
    if host in doc:
        del doc[host]  # type: ignore[arg-type]
        return
    # Unquoted nested format: [bitbucket.org] → doc["bitbucket"]["org"]
    parts = host.split(".")
    node: object = doc
    for part in parts[:-1]:
        if not isinstance(node, dict):
            return
        node = node.get(part)
    if isinstance(node, dict) and parts[-1] in node:
        del node[parts[-1]]  # type: ignore[arg-type]


# ── Public legacy API (test_auth.py) ─────────────────────────────────────────

def load_credentials() -> Credentials:
    _load_dot_env()
    src = credential_source()
    token = _token_from_source(src)
    if not token:
        raise AuthError(
            "No Bitbucket token found. Run `bb auth login` to authenticate."
        )
    username = _username_from_hosts() if src == "hosts.toml" else ""
    return Credentials(token=token, username=username)


def credential_source() -> str:
    _load_dot_env()
    for name in TOKEN_VARS:
        if os.environ.get(name):
            return f"env:{name}"
    if _hosts_token():
        return "hosts.toml"
    return "none"


def save_credentials(creds: Credentials) -> None:
    path = _hosts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    doc["token"] = creds.token
    doc["username"] = creds.username
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def clear_credentials() -> None:
    path = _hosts_path()
    if path.exists():
        path.unlink()


# ── Internal helpers (patchable in tests) ─────────────────────────────────────

def _hosts_path() -> Path:
    return Path(user_config_dir("bb")) / "hosts.toml"


def _read_hosts() -> tomlkit.TOMLDocument:
    path = _hosts_path()
    if not path.is_file():
        return tomlkit.document()
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return tomlkit.document()


def _write_hosts(doc: tomlkit.TOMLDocument) -> None:
    path = _hosts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _env_token() -> Credential | None:
    for name in TOKEN_VARS:
        val = os.environ.get(name, "")
        if val:
            return Credential(token=val, source=f"env:{name}")
    return None


def _find_repo_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _find_dotenv() -> Path | None:
    cwd = Path.cwd()
    if (cwd / ".env").is_file():
        return cwd / ".env"
    root = _find_repo_root()
    if root is None:
        return None
    dotenv = root / ".env"
    return dotenv if dotenv.is_file() else None


def _read_denv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key in TOKEN_VARS:
            result[key] = val
    return result


def _denv_token() -> Credential | None:
    path = _find_dotenv()
    if path is None:
        return None
    pairs = _read_denv(path)
    for name in TOKEN_VARS:
        val = pairs.get(name, "")
        if val:
            return Credential(token=val, source=f"dotenv:{name}")
    return None


def _entry_for_host(doc: tomlkit.TOMLDocument, host: str) -> dict | None:
    # Quoted key: ["bitbucket.org"] → doc["bitbucket.org"]
    entry = doc.get(host)
    if entry and isinstance(entry, dict):
        return entry
    # Unquoted TOML section [bitbucket.org] creates nested tables
    # e.g. doc["bitbucket"]["org"] for host "bitbucket.org"
    parts = host.split(".")
    node: object = doc
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, dict) and node.get("token"):
        return node
    return None


def _cred_from_file(host: str) -> Credential | None:
    doc = _read_hosts()
    entry = _entry_for_host(doc, host)
    if entry:
        token = str(entry.get("token", ""))
        if token:
            return Credential(
                token=token,
                host=host,
                auth_type=str(entry.get("auth_type", "bearer")),
                username=str(entry.get("username", "")),
                source="hosts",
            )
    flat_token = _hosts_token()
    if flat_token:
        return Credential(
            token=flat_token,
            host=host,
            auth_type="bearer",
            username=_username_from_hosts(),
            source="hosts",
        )
    return None


def _load_dot_env() -> None:
    root = _find_repo_root()
    if root is None:
        return
    dot_env = root / ".env"
    if not dot_env.exists():
        return
    _parse_env_file(dot_env)


def _parse_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _hosts_token() -> str:
    doc = _read_hosts()
    return str(doc.get("token", ""))


def _username_from_hosts() -> str:
    doc = _read_hosts()
    return str(doc.get("username", ""))


def _token_from_source(src: str) -> str:
    if src.startswith("env:"):
        return os.environ.get(src[4:], "")
    if src == "hosts.toml":
        return _hosts_token()
    return ""


# Compatibility alias for test_cfg.py
_cred_from_dotenv = _denv_token
