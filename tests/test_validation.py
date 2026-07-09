"""Tests for Pydantic validation gates."""
from __future__ import annotations

import pytest

from bb.core.errors import BBError, ConfigError, ContextError
from bb.core.validation import (
    validate_auth_type,
    validate_base_url,
    validate_limit,
    validate_method,
    validate_repo_parts,
)


def test_validate_base_url_strips_bitbucket_route() -> None:
    assert (
        validate_base_url("https://bitbucket.polariswireless.com/plugins/servlet/access-tokens/users/u/manage")
        == "https://bitbucket.polariswireless.com"
    )


def test_validate_base_url_rejects_bad_value() -> None:
    with pytest.raises(ConfigError):
        validate_base_url("not a host with spaces")


def test_validate_repo_parts_accepts_project_repo() -> None:
    assert validate_repo_parts("PVA", "radio") == ("PVA", "radio")


def test_validate_repo_parts_rejects_nested_repo() -> None:
    with pytest.raises(ContextError):
        validate_repo_parts("PVA", "team/radio")


def test_validate_auth_type_accepts_bearer() -> None:
    assert validate_auth_type("bearer") == "bearer"


def test_validate_auth_type_accepts_basic() -> None:
    assert validate_auth_type("basic") == "basic"


def test_validate_auth_type_rejects_unknown() -> None:
    with pytest.raises(BBError):
        validate_auth_type("oauth")


def test_validate_limit_rejects_over_max() -> None:
    with pytest.raises(BBError):
        validate_limit(1001)


def test_validate_method_accepts_lowercase_get() -> None:
    assert validate_method("get") == "GET"


def test_validate_method_rejects_trace() -> None:
    with pytest.raises(BBError):
        validate_method("TRACE")


def test_validate_limit_accepts_one() -> None:
    assert validate_limit(1) == 1


def test_validate_limit_rejects_zero() -> None:
    with pytest.raises(BBError):
        validate_limit(0)
