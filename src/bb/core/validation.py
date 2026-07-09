"""
validation.py — Pydantic gates for user-facing CLI input.

Inputs : raw strings/ints from Typer, env vars, TOML config.
Outputs: normalized values.
Failure: ConfigError/ContextError/BBError with concise remediation.
"""
from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator

from bb.core.deployment import normalize_base_url
from bb.core.errors import BBError, ConfigError, ContextError


class BaseUrlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str

    @field_validator("value")
    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = normalize_base_url(value)
        # HttpUrl is intentionally used as a gate while preserving our normalized string.
        HttpUrl(normalized)
        return normalized


class RepoRefInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str = Field(min_length=1)
    repo: str = Field(min_length=1)

    @field_validator("project", "repo")
    @classmethod
    def no_empty_or_nested_parts(cls, value: str) -> str:
        if "/" in value or value.strip() != value:
            raise ValueError("must be one non-empty path segment")
        return value


class AuthTypeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Literal["bearer", "basic"]


class MethodInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class PositiveLimitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(ge=1, le=1000)


def validate_base_url(value: str) -> str:
    try:
        return BaseUrlInput(value=value).value
    except ValidationError as exc:
        raise ConfigError(_message("invalid base_url", exc)) from exc


def validate_repo_parts(project: str, repo: str) -> tuple[str, str]:
    try:
        ref = RepoRefInput(project=project, repo=repo)
    except ValidationError as exc:
        raise ContextError(_message("invalid repo", exc)) from exc
    return ref.project, ref.repo


def validate_auth_type(value: str) -> str:
    try:
        return AuthTypeInput(value=cast(Literal["bearer", "basic"], value)).value
    except ValidationError as exc:
        raise BBError("invalid auth type; expected bearer or basic") from exc


def validate_method(value: str) -> str:
    try:
        return MethodInput(value=cast(Literal["GET", "POST", "PUT", "PATCH", "DELETE"], value.upper())).value
    except ValidationError as exc:
        raise BBError("invalid HTTP method; expected GET, POST, PUT, PATCH, or DELETE") from exc


def validate_limit(value: int) -> int:
    try:
        return PositiveLimitInput(value=value).value
    except ValidationError as exc:
        raise BBError("invalid limit; expected an integer from 1 to 1000") from exc


def _message(prefix: str, exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "value"
    msg = str(first.get("msg", "invalid value"))
    return f"{prefix}: {loc} {msg}"
