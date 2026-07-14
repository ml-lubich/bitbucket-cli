"""Smoke tests: every command group responds to --help with exit 0."""
from __future__ import annotations

from typer.testing import CliRunner

runner = CliRunner()


def test_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_short_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0


def test_help_command_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0


def test_help_command_accepts_group() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["help", "repo"])
    assert result.exit_code == 0


def test_version_contains_version_string() -> None:
    from bb import __version__
    from bb.cli import app
    result = runner.invoke(app, ["--version"])
    assert __version__ in result.output


def test_auth_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


def test_pr_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0


def test_repo_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["repo", "--help"])
    assert result.exit_code == 0


def test_repo_short_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["repo", "-h"])
    assert result.exit_code == 0


def test_repo_list_short_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["repo", "list", "-h"])
    assert result.exit_code == 0


def test_api_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["api", "--help"])
    assert result.exit_code == 0


def test_config_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0


def test_issue_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["issue", "--help"])
    assert result.exit_code == 0


def test_search_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0


def test_status_help_exits_zero() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0


def test_top_level_help_lists_search_and_status() -> None:
    from bb.cli import app
    result = runner.invoke(app, ["--help"])
    assert "search" in result.output
    assert "status" in result.output
