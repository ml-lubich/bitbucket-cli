# Runbook

## First-time setup

```bash
git clone https://github.com/ml-lubich/bitbucket-cli
cd bitbucket-cli
./scripts/setup.sh
```

`scripts/setup.sh` installs `uv` if missing and runs `uv sync`. Safe to re-run.

## How to run

```bash
uv run bb --help
uv run bb auth login --token ${BB_TOKEN}
uv run bb pr list
```

Once installed with `uv tool install .`, the `bb` command is available directly:

```bash
bb pr list
bb pipeline logs abc123
```

## Creating a Bitbucket token

1. Log in to Bitbucket Cloud.
2. Go to **Personal settings → API tokens** (or **App passwords** for older accounts).
3. Create a token with the scopes you need:
   - `repository` — repo read/clone/write
   - `pullrequest` — PR read/write
   - `pipeline` — pipeline read/run
   - `issue` — issue tracker read/write
   - `snippet` — snippets read/write
   - `project` — projects read/write
   - `workspace:read` — workspace and member listing
4. Copy the token immediately — Bitbucket shows it only once.
5. Store it: `bb auth login --token ${BB_TOKEN}` or set `BB_TOKEN` in your environment or `.env` file.

## Common failures

| Symptom | Cause | Resolution |
|---|---|---|
| `bb: No Bitbucket token found.` | No credentials configured | `bb auth login --token ${BB_TOKEN}` |
| `bb: API 401: ...` | Token expired or revoked | Rotate token; `bb auth logout && bb auth login --token ${NEW_TOKEN}` |
| `bb: API 404: ...` on `bb issue list` | Issue tracker disabled for repo | Enable it in Bitbucket repo settings → Issue tracker |
| `bb: no bitbucket remote` | Not in a Bitbucket-hosted repo | Pass `-R workspace/slug` or set `BB_REPO=workspace/slug` |
| `bb: API 404: ...` on `bb repo ...` | Repo slug or workspace wrong | Verify with `bb repo list --workspace myworkspace` |
| Pipelines UUID error | UUID not quoted correctly | Pass UUID as-is; `bb` handles `{uuid}` quoting in URL path |

## Credential rotation

```bash
bb auth logout
bb auth login --token ${NEW_TOKEN}
```

Or update `BB_TOKEN` in your environment / `.env` file without touching `hosts.toml`.

## How to add a new command group

1. Create `src/bb/commands/<group>.py` with a `typer.Typer` instance named `app`.
2. Implement subcommands as `@app.command()` functions; import from `core/` only.
3. Add an entry to `_GROUPS` in `src/bb/cli.py`:
   ```python
   from bb.commands import mygroup
   _GROUPS["mygroup"] = mygroup.app
   ```
4. Add tests under `tests/commands/test_mygroup.py` using `httpx.MockTransport`.
5. Update `docs/API.md` with the new group's commands and flags in the same PR.
6. Run `uv run pytest` — must exit 0 before merging.
