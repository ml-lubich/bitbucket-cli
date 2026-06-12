"""Smoke tests: every command group responds to --help with exit 0."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

runner = CliRunner()


def test_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version_contains_version_string() -> None:
    from bb.main import app
    result = runner.invoke(app, ["--version"])
    assert "0.1.0" in result.output


def test_auth_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


def test_pr_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0


def test_repo_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["repo", "--help"])
    assert result.exit_code == 0


def test_api_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["api", "--help"])
    assert result.exit_code == 0


def test_config_help_exits_zero() -> None:
    from bb.main import app
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
