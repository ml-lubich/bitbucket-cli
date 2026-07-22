from __future__ import annotations

from typer.testing import CliRunner

from bb.cli import app

runner = CliRunner()


def test_version_exits_zero() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0


def test_version_output_contains_version() -> None:
    from bb import __version__

    result = runner.invoke(app, ["--version"])
    assert __version__ in result.output


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_help_lists_pr_group() -> None:
    result = runner.invoke(app, ["--help"])
    assert "pr" in result.output


def test_help_lists_repo_group() -> None:
    result = runner.invoke(app, ["--help"])
    assert "repo" in result.output


def test_help_lists_issue_group() -> None:
    result = runner.invoke(app, ["--help"])
    assert "issue" in result.output
