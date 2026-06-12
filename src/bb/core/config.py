"""
config.py — Non-secret settings with documented precedence.

Inputs : env BB_GIT_PROTOCOL / BB_EDITOR / BB_WORKSPACE, cwd/bb.toml,
         <user_config_dir("bb")>/config.toml.
Outputs: Settings dataclass; set_user_value writes the user config.toml.
Failure: ConfigError on unknown keys. Secrets live in auth.py, never here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from platformdirs import user_config_dir

from bb.core.errors import ConfigError

_VALID_KEYS = {"git_protocol", "editor", "default_repo", "default_workspace"}
_ENV_MAP = {
    "BB_GIT_PROTOCOL": "git_protocol",
    "BB_EDITOR": "editor",
    "BB_REPO": "default_repo",
    "BB_WORKSPACE": "default_workspace",
}


@dataclass(frozen=True)
class Settings:
    git_protocol: str = "https"
    editor: str = ""
    default_repo: str = ""
    default_workspace: str = ""


def _user_cfg_path() -> Path:
    return Path(user_config_dir("bb")) / "config.toml"


def _proj_cfg_path() -> Path:
    return Path.cwd() / "bb.toml"


def _load_toml(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in doc.items() if k in _VALID_KEYS}


def _apply_env(base: dict[str, str]) -> dict[str, str]:
    result = dict(base)
    for env_key, field_name in _ENV_MAP.items():
        val = os.environ.get(env_key, "")
        if val:
            result[field_name] = val
    return result


def load_settings() -> Settings:
    merged: dict[str, str] = {}
    merged.update(_load_toml(_user_cfg_path()))
    merged.update(_load_toml(_proj_cfg_path()))
    merged = _apply_env(merged)
    return Settings(
        git_protocol=merged.get("git_protocol", "https"),
        editor=merged.get("editor", ""),
        default_repo=merged.get("default_repo", ""),
        default_workspace=merged.get("default_workspace", ""),
    )


def get_value(key: str) -> str:
    if key not in _VALID_KEYS:
        raise ConfigError(f"unknown key {key!r}; valid: {sorted(_VALID_KEYS)}")
    data = _load_toml(_user_cfg_path())
    defaults = {"git_protocol": "https"}
    return data.get(key, defaults.get(key, ""))


def set_user_value(key: str, value: str) -> None:
    if key not in _VALID_KEYS:
        raise ConfigError(f"unknown key {key!r}; valid: {sorted(_VALID_KEYS)}")
    path = _user_cfg_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
    doc[key] = value  # type: ignore[index]
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


# Alias kept for internal callers
set_value = set_user_value
