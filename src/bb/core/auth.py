"""
auth.py — Credential resolution + persistent token store.

Inputs : env BB_TOKEN > BITBUCKET_TOKEN > BITBUCKET_AUTH_TOKEN > .env file
         > OS keyring (macOS Keychain / XDG Secret Service) > hosts.toml fallback.
Outputs: Credential; token in keyring when available, else hosts.toml mode 0600.
Failure: AuthError when no credential found. Tokens never logged.
"""
from __future__ import annotations

import base64
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from platformdirs import user_config_dir

from bb.core.deployment import CLOUD_HOST
from bb.core.errors import AuthError

HOST = CLOUD_HOST
TOKEN_VARS = ("BB_TOKEN", "BITBUCKET_TOKEN", "BITBUCKET_AUTH_TOKEN")
# Atlassian account API tokens (ATATT…) only work as Basic auth with the
# account email — an email var upgrades env/.env tokens to basic.
EMAIL_VARS = ("BITBUCKET_EMAIL", "BB_USERNAME")
KEYRING_SERVICE = "bb"


# ── New API (used by ApiClient, commands) ─────────────────────────────────────

@dataclass(frozen=True)
class Credential:
    token: str
    host: str = HOST
    auth_type: str = "bearer"  # "bearer" | "basic"
    username: str = ""
    source: str = "keyring"  # "env:<NAME>" | "dotenv:<NAME>" | "keyring" | "hosts"


# ── Legacy API (test_auth.py, test_client.py compat) ─────────────────────────

@dataclass(frozen=True)
class Credentials:
    token: str
    username: str = ""


# ── Public new API ────────────────────────────────────────────────────────────

def masked(token: str) -> str:
    return token[:4] + "****"


def authorization_header(cred: Credential) -> str:
    """Build the HTTP Authorization header value for API and git HTTPS."""
    if cred.username:
        raw = base64.b64encode(f"{cred.username}:{cred.token}".encode()).decode()
        return f"Basic {raw}"
    return f"Bearer {cred.token}"


def git_https_config_args(cred: Credential) -> list[str]:
    """Return `git -c` args so HTTPS clone/fetch uses the stored credential."""
    return ["-c", f"http.extraHeader=Authorization: {authorization_header(cred)}"]


def git_command(args: list[str], *, https_auth: bool = False, host: str = HOST) -> list[str]:
    """Build a git argv list, optionally injecting HTTPS auth from resolve_credential."""
    cmd = ["git"]
    if https_auth:
        cmd.extend(git_https_config_args(resolve_credential(host=host)))
    cmd.extend(args)
    return cmd


def resolve_credential(host: str = HOST) -> Credential:
    cred = _env_token(host)
    if cred:
        return cred
    cred = _denv_token(host)
    if cred:
        return cred
    cred = _cred_from_keyring(host)
    if cred:
        return cred
    file_cred = _cred_from_file(host)
    if file_cred:
        return file_cred
    raise AuthError("not authenticated — run `bb auth login` or set BB_TOKEN")


def stored_credential(host: str = HOST) -> Credential:
    cred = _cred_from_keyring(host) or _cred_from_file(host)
    if not cred:
        raise AuthError(f"no stored credential for {host!r}")
    return cred


def save_credential(cred: Credential) -> Path:
    """Persist credential globally. Prefer OS keyring; fall back to hosts.toml."""
    meta = {"auth_type": cred.auth_type, "username": cred.username}
    if _keyring_set(cred.host, cred.token, meta):
        _write_hosts_meta(cred.host, auth_type=cred.auth_type, username=cred.username, storage="keyring")
        return _hosts_path()
    # Fallback: plaintext file with mode 0600 (CI / headless without keyring).
    doc = _read_hosts()
    entry = tomlkit.table()
    entry.add("token", cred.token)
    entry.add("auth_type", cred.auth_type)
    entry.add("storage", "file")
    if cred.username:
        entry.add("username", cred.username)
    doc[cred.host] = entry
    _write_hosts(doc)
    return _hosts_path()


def delete_credential(host: str = HOST) -> bool:
    removed_keyring = _keyring_delete(host)
    doc = _read_hosts()
    had_file = _entry_for_host(doc, host) is not None or bool(_hosts_token())
    if had_file:
        _del_host_entry(doc, host)
        # Also clear legacy flat keys if present
        if "token" in doc:
            del doc["token"]
        if "username" in doc:
            del doc["username"]
        path = _hosts_path()
        if not _hosts_has_entries(doc):
            if path.exists():
                path.unlink()
        else:
            _write_hosts(doc)
    return removed_keyring or had_file


def _del_host_entry(doc: tomlkit.TOMLDocument, host: str) -> None:
    if host in doc:
        del doc[host]
        return
    parts = host.split(".")
    node: object = doc
    for part in parts[:-1]:
        if not isinstance(node, dict):
            return
        node = node.get(part)
    if isinstance(node, dict) and parts[-1] in node:
        del node[parts[-1]]


def _hosts_has_entries(doc: tomlkit.TOMLDocument) -> bool:
    if not doc.body:
        return False
    return any(isinstance(item[1], tomlkit.items.Table) for item in doc.body)


# ── Public legacy API (test_auth.py) ─────────────────────────────────────────

def load_credentials() -> Credentials:
    _load_dot_env()
    src = credential_source()
    token = _token_from_source(src)
    if not token:
        raise AuthError(
            "No Bitbucket token found. Run `bb auth login` to authenticate."
        )
    username = ""
    if src in ("hosts.toml", "keyring"):
        stored = _cred_from_keyring(HOST) or _cred_from_file(HOST)
        username = stored.username if stored else _username_from_hosts()
    return Credentials(token=token, username=username)


def credential_source() -> str:
    _load_dot_env()
    for name in TOKEN_VARS:
        if os.environ.get(name):
            return f"env:{name}"
    if _cred_from_keyring(HOST):
        return "keyring"
    if _cred_from_file(HOST):
        return "hosts.toml"
    return "none"


def save_credentials(creds: Credentials) -> None:
    save_credential(Credential(token=creds.token, username=creds.username))


def clear_credentials() -> None:
    delete_credential(HOST)
    path = _hosts_path()
    if path.exists():
        path.unlink()


# ── Keyring helpers (patchable in tests) ──────────────────────────────────────

def _keyring_set(host: str, token: str, meta: dict[str, str]) -> bool:
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError:
        return False
    payload = json.dumps({"token": token, **meta})
    try:
        keyring.set_password(KEYRING_SERVICE, host, payload)
        return True
    except KeyringError:
        return False
    except Exception:
        return False


def _keyring_get(host: str) -> dict[str, str] | None:
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError:
        return None
    try:
        raw = keyring.get_password(KEYRING_SERVICE, host)
    except KeyringError:
        return None
    except Exception:
        return None
    if not raw:
        return None
    # New format: JSON blob. Legacy: bare token string.
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"token": raw, "auth_type": "bearer", "username": ""}
        if not isinstance(data, dict) or not data.get("token"):
            return None
        return {
            "token": str(data["token"]),
            "auth_type": str(data.get("auth_type") or "bearer"),
            "username": str(data.get("username") or ""),
        }
    return {"token": raw, "auth_type": "bearer", "username": ""}


def _keyring_delete(host: str) -> bool:
    try:
        import keyring
        from keyring.errors import KeyringError, PasswordDeleteError
    except ImportError:
        return False
    try:
        keyring.delete_password(KEYRING_SERVICE, host)
        return True
    except PasswordDeleteError:
        return False
    except KeyringError:
        return False
    except Exception:
        return False


def _cred_from_keyring(host: str) -> Credential | None:
    data = _keyring_get(host)
    if not data:
        return None
    return Credential(
        token=data["token"],
        host=host,
        auth_type=data.get("auth_type", "bearer"),
        username=data.get("username", ""),
        source="keyring",
    )


def _write_hosts_meta(
    host: str,
    *,
    auth_type: str,
    username: str,
    storage: str,
) -> None:
    """Write non-secret host metadata; token lives in keyring."""
    doc = _read_hosts()
    entry = tomlkit.table()
    entry.add("auth_type", auth_type)
    entry.add("storage", storage)
    if username:
        entry.add("username", username)
    doc[host] = entry
    _write_hosts(doc)


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


def _email_value(pairs: dict[str, str]) -> str:
    for name in EMAIL_VARS:
        val = os.environ.get(name, "") or pairs.get(name, "")
        if val:
            return val
    return ""


def _with_email(token: str, source: str, pairs: dict[str, str], host: str = HOST) -> Credential:
    email = _email_value(pairs)
    if email:
        return Credential(token=token, host=host, auth_type="basic", username=email, source=source)
    return Credential(token=token, host=host, source=source)


def _env_token(host: str = HOST) -> Credential | None:
    for name in TOKEN_VARS:
        val = os.environ.get(name, "")
        if val:
            return _with_email(val, f"env:{name}", _denv_pairs(), host)
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
        if key in TOKEN_VARS or key in EMAIL_VARS:
            result[key] = val
    return result


def _denv_pairs() -> dict[str, str]:
    path = _find_dotenv()
    if path is None:
        return {}
    return _read_denv(path)


def _denv_token(host: str = HOST) -> Credential | None:
    pairs = _denv_pairs()
    for name in TOKEN_VARS:
        val = pairs.get(name, "")
        if val:
            return _with_email(val, f"dotenv:{name}", pairs, host)
    return None


def _entry_for_host(doc: tomlkit.TOMLDocument, host: str) -> dict | None:
    entry = doc.get(host)
    if entry and isinstance(entry, dict):
        return entry
    parts = host.split(".")
    node: object = doc
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, dict) and (node.get("token") or node.get("storage")):
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
        # Metadata-only entry (token in keyring) — already tried keyring above.
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
    if src == "keyring":
        data = _keyring_get(HOST)
        return data["token"] if data else ""
    if src == "hosts.toml":
        cred = _cred_from_file(HOST)
        return cred.token if cred else _hosts_token()
    return ""


# Compatibility alias for test_cfg.py
_cred_from_dotenv = _denv_token
