"""bb — Bitbucket Cloud CLI."""
from __future__ import annotations

from pathlib import Path

import typer

from bb.commands import auth, pr, repo, issue, pipeline, branch
from bb.commands import workspace, project, snippet, api, config_cmd, browse


app = typer.Typer(name="bb", help="Bitbucket Cloud CLI", no_args_is_help=True)

_GROUPS = {
    "auth": auth.app,
    "pr": pr.app,
    "repo": repo.app,
    "issue": issue.app,
    "pipeline": pipeline.app,
    "branch": branch.app,
    "workspace": workspace.app,
    "project": project.app,
    "snippet": snippet.app,
    "api": api.app,
    "config": config_cmd.app,
}

for _name, _sub in _GROUPS.items():
    app.add_typer(_sub, name=_name)

app.command("browse")(browse.browse)


def _version_callback(value: bool) -> None:
    if value:
        version = (Path(__file__).parent.parent.parent / "VERSION").read_text().strip()
        typer.echo(version)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    pass
