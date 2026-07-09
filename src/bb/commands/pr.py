"""
pr.py — Pull request commands for Bitbucket Cloud.
Inputs: Credential (via resolve_credential), RepoContext (via current_repo or --repo).
Outputs: tables or JSON to stdout; PR links on create.
Failure modes: ApiError, ContextError, BBError.
"""
from __future__ import annotations

import subprocess
import webbrowser
from collections.abc import Callable

import typer

from bb.core.auth import git_command
from bb.core.client import ApiClient
from bb.core.client import make_client as make_api_client
from bb.core.config import load_settings
from bb.core.context import RepoContext, current_branch, current_repo
from bb.core.deployment import deployment_from_base_url
from bb.core.errors import BBError
from bb.core.output import print_json, print_table
from bb.core.validation import validate_limit

app = typer.Typer(help="Manage pull requests")


def make_client(repo: str = "") -> tuple[ApiClient, RepoContext]:
    ctx = current_repo(override=repo)
    return make_api_client(base_url=ctx.base_url), ctx


def _pr_base(ctx: RepoContext) -> str:
    return f"/repositories/{ctx.workspace}/{ctx.repo}/pullrequests"


@app.command("list")
def pr_list(
    repo: str = typer.Option("", "--repo", "-R"),
    state: str = typer.Option("OPEN", "--state"),
    limit: int = typer.Option(30, "--limit"),
    reviewer: str = typer.Option("", "--reviewer"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List pull requests."""
    limit = validate_limit(limit)
    client, ctx = make_client(repo)
    params = _build_list_params(client, ctx, state, limit, reviewer)
    items = list(client.paginate(_pr_base(ctx), **params))
    if as_json:
        print_json(items)
        return
    rows = [_pr_row(p) for p in items]
    print_table(["ID", "TITLE", "BRANCH", "AUTHOR", "STATE"], rows)


def _build_list_params(
    client: ApiClient,
    ctx: RepoContext,
    state: str,
    limit: int,
    reviewer: str,
) -> dict[str, str | int]:
    params: dict[str, str | int] = {"state": state, "pagelen": limit}
    if reviewer == "@me":
        me = client.get("/user")
        uuid = me.get("uuid", "")
        params["q"] = f'reviewers.uuid="{uuid}"'
    elif reviewer:
        params["q"] = f'reviewers.nickname="{reviewer}"'
    return params


def _pr_row(p: dict) -> tuple[str, ...]:
    pr_id = str(p.get("id", ""))
    title = str(p.get("title", ""))
    branch = str(p.get("source", {}).get("branch", {}).get("name", ""))
    author = str(p.get("author", {}).get("display_name", ""))
    state = str(p.get("state", ""))
    return pr_id, title, branch, author, state


@app.command("create")
def pr_create(
    repo: str = typer.Option("", "--repo", "-R"),
    title: str = typer.Option("", "--title"),
    body: str = typer.Option("", "--body"),
    base: str = typer.Option("", "--base"),
    head: str = typer.Option("", "--head"),
    draft: bool = typer.Option(False, "--draft"),
    close_source_branch: bool = typer.Option(False, "--close-source-branch"),
) -> None:
    """Create a pull request."""
    client, ctx = make_client(repo)
    resolved_title = title or _last_commit_message()
    resolved_head = head or current_branch()
    resolved_base = base or _repo_mainbranch(client, ctx)
    payload = _build_create_payload(
        ctx, resolved_title, body, resolved_base, resolved_head,
        draft, close_source_branch,
    )
    result = client.post(_pr_base(ctx), json_body=payload)
    pr_id = result.get("id", "")
    pr_url = result.get("links", {}).get("html", {}).get("href", "")
    typer.echo(f"Created PR #{pr_id}: {pr_url}")


def _build_create_payload(
    ctx: RepoContext,
    title: str,
    body: str,
    base: str,
    head: str,
    draft: bool,
    close_source: bool,
) -> dict:
    payload: dict = {
        "title": title,
        "source": {"branch": {"name": head}},
        "destination": {"branch": {"name": base}},
        "close_source_branch": close_source,
        "draft": draft,
    }
    if body:
        payload["description"] = body
    return payload


@app.command("view")
def pr_view(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    as_json: bool = typer.Option(False, "--json"),
    web: bool = typer.Option(False, "--web"),
) -> None:
    """View a pull request."""
    client, ctx = make_client(repo)
    pr = client.get(f"{_pr_base(ctx)}/{pr_id}")
    if web:
        url = pr.get("links", {}).get("html", {}).get("href", "")
        webbrowser.open(url)
        return
    if as_json:
        print_json(pr)
        return
    _print_pr_detail(pr)


def _print_pr_detail(pr: dict) -> None:
    title = pr.get("title", "")
    state = pr.get("state", "")
    author = pr.get("author", {}).get("display_name", "")
    src = pr.get("source", {}).get("branch", {}).get("name", "")
    dst = pr.get("destination", {}).get("branch", {}).get("name", "")
    created = pr.get("created_on", "")
    desc = pr.get("description", "")
    typer.echo(f"Title:  {title}")
    typer.echo(f"State:  {state}")
    typer.echo(f"Author: {author}")
    typer.echo(f"Branch: {src} → {dst}")
    typer.echo(f"Created: {created}")
    if desc:
        typer.echo(f"\n{desc}")


@app.command("checkout")
def pr_checkout(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
) -> None:
    """Checkout the branch of a pull request."""
    client, ctx = make_client(repo)
    pr = client.get(f"{_pr_base(ctx)}/{pr_id}")
    branch = pr["source"]["branch"]["name"]
    clone_url = _pr_clone_url(pr, ctx)
    host = deployment_from_base_url(ctx.base_url or load_settings().base_url).host
    subprocess.run(git_command(["fetch", clone_url, branch], https_auth=True, host=host), check=True)
    subprocess.run(["git", "checkout", branch], check=True)


def _pr_clone_url(pr: dict, ctx: RepoContext) -> str:
    src_repo = pr.get("source", {}).get("repository", {})
    links = src_repo.get("links", {}).get("clone", [])
    for link in links:
        if link.get("name") == "https":
            return str(link["href"])
    if ctx.base_url:
        return f"{ctx.base_url}/scm/{ctx.workspace}/{ctx.repo}.git"
    return f"https://bitbucket.org/{ctx.workspace}/{ctx.repo}.git"


@app.command("merge")
def pr_merge(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    merge_strategy: str = typer.Option("merge_commit", "--merge-strategy"),
    delete_branch: bool = typer.Option(False, "--delete-branch"),
    message: str = typer.Option("", "--message"),
) -> None:
    """Merge a pull request."""
    client, ctx = make_client(repo)
    payload: dict = {"merge_strategy": merge_strategy, "close_source_branch": delete_branch}
    if message:
        payload["message"] = message
    client.post(f"{_pr_base(ctx)}/{pr_id}/merge", json_body=payload)
    typer.echo(f"PR #{pr_id} merged.")


@app.command("close")
def pr_close(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
) -> None:
    """Decline a pull request."""
    client, ctx = make_client(repo)
    client.post(f"{_pr_base(ctx)}/{pr_id}/decline")
    typer.echo(f"PR #{pr_id} declined.")


@app.command("reopen")
def pr_reopen(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
) -> None:
    """Reopen a declined pull request (not supported)."""
    raise BBError(
        "Bitbucket Cloud cannot reopen a declined PR; "
        "create a new one with `bb pr create`"
    )


@app.command("edit")
def pr_edit(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    title: str = typer.Option("", "--title"),
    body: str = typer.Option("", "--body"),
    base: str = typer.Option("", "--base"),
) -> None:
    """Edit a pull request."""
    client, ctx = make_client(repo)
    payload = _build_edit_payload(title, body, base)
    if not payload:
        raise BBError("Provide at least one of --title, --body, --base")
    result = client.put(f"{_pr_base(ctx)}/{pr_id}", json_body=payload)
    typer.echo(f"PR #{result.get('id', pr_id)} updated.")


def _build_edit_payload(title: str, body: str, base: str) -> dict:
    payload: dict = {}
    if title:
        payload["title"] = title
    if body:
        payload["description"] = body
    if base:
        payload["destination"] = {"branch": {"name": base}}
    return payload


@app.command("review")
def pr_review(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    approve: bool = typer.Option(False, "--approve"),
    request_changes: bool = typer.Option(False, "--request-changes"),
    unapprove: bool = typer.Option(False, "--unapprove"),
    body: str = typer.Option("", "--body"),
) -> None:
    """Approve, unapprove, or request changes on a PR."""
    client, ctx = make_client(repo)
    _dispatch_review(client, ctx, pr_id, approve, request_changes, unapprove)
    if body:
        client.post(
            f"{_pr_base(ctx)}/{pr_id}/comments",
            json_body={"content": {"raw": body}},
        )


def _dispatch_review(
    client: ApiClient,
    ctx: RepoContext,
    pr_id: int,
    approve: bool,
    request_changes: bool,
    unapprove: bool,
) -> None:
    base = f"{_pr_base(ctx)}/{pr_id}"
    actions: dict[str, Callable[[], object]] = {
        "approve": lambda: client.post(f"{base}/approve"),
        "request_changes": lambda: client.post(f"{base}/request-changes"),
        "unapprove": lambda: client.delete(f"{base}/approve"),
    }
    flag_map = {"approve": approve, "request_changes": request_changes, "unapprove": unapprove}
    chosen = [k for k, v in flag_map.items() if v]
    if len(chosen) != 1:
        raise BBError("Provide exactly one of --approve, --request-changes, --unapprove")
    actions[chosen[0]]()
    typer.echo(f"PR #{pr_id}: {chosen[0]} applied.")


@app.command("comment")
def pr_comment(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
    body: str = typer.Option(..., "--body"),
) -> None:
    """Post a comment on a pull request."""
    client, ctx = make_client(repo)
    client.post(
        f"{_pr_base(ctx)}/{pr_id}/comments",
        json_body={"content": {"raw": body}},
    )
    typer.echo("Comment posted.")


@app.command("diff")
def pr_diff(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
) -> None:
    """Show the diff of a pull request."""
    client, ctx = make_client(repo)
    text = client.raw_get(f"{_pr_base(ctx)}/{pr_id}/diff")
    typer.echo(text)


@app.command("checks")
def pr_checks(
    pr_id: int = typer.Argument(...),
    repo: str = typer.Option("", "--repo", "-R"),
) -> None:
    """Show build statuses for a pull request."""
    client, ctx = make_client(repo)
    items = list(client.paginate(f"{_pr_base(ctx)}/{pr_id}/statuses"))
    rows = [_status_row(s) for s in items]
    print_table(["NAME", "STATE", "DESCRIPTION", "URL"], rows)


def _status_row(s: dict) -> tuple[str, ...]:
    name = str(s.get("name", ""))
    state = str(s.get("state", ""))
    desc = str(s.get("description", ""))
    url = str(s.get("url", ""))
    return name, state, desc, url


# ── helpers ───────────────────────────────────────────────────────────────────

def _last_commit_message() -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _repo_mainbranch(client: ApiClient, ctx: RepoContext) -> str:
    info = client.get(f"/repositories/{ctx.workspace}/{ctx.repo}")
    return str(info.get("mainbranch", {}).get("name", "main"))
