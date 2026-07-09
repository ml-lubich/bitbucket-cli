# Runbook

## First-time setup

```bash
git clone https://github.com/ml-lubich/bitbucket-cli
cd bitbucket-cli
./scripts/setup.sh
```

`scripts/setup.sh` installs `uv` if missing, creates `venv/`, then runs
`uv sync`. Safe to re-run after `git pull`.

## How to run

From the repo root with `uv run`:

```bash
UV_PROJECT_ENVIRONMENT=venv uv run bb --help
UV_PROJECT_ENVIRONMENT=venv uv run bb auth login
UV_PROJECT_ENVIRONMENT=venv uv run bb pr list
```

After installing globally with `uv tool install .`, the `bb` command is
available directly:

```bash
bb pr list
bb pipeline logs abc123
```

For Polaris Bitbucket Data Center:

```bash
bb config set base_url https://bitbucket.polariswireless.com
bb auth login
bb doctor
```

## Creating a Bitbucket token

### Bitbucket Cloud

1. Log in to Bitbucket Cloud.
2. Go to **Personal settings -> API tokens** (or **App passwords** for older
   accounts that do not yet support API tokens).
3. Create a token or app password with the scopes you need:
   - `repository` — repo read / clone / write
   - `pullrequest` — PR read / write
   - `pipeline` — pipeline read / trigger
   - `issue` — issue tracker read / write
   - `snippet` — snippets read / write
   - `project` — projects read / write
   - `workspace:read` — workspace and member listing
4. Copy the token immediately — Bitbucket shows it only once.
5. Store it:

```bash
bb auth login                        # prompts securely; stores in OS keyring
# or:
export BB_TOKEN=${BB_TOKEN}
bb auth login --token ${BB_TOKEN}
# or pipe:
echo "${BB_TOKEN}" | bb auth login --with-token
```

Never commit the token value. Use `${BB_TOKEN}` placeholders in scripts
and CI secret stores. The token is stored once in the OS keyring (or
`hosts.toml` mode 0600 if no keyring is available) and reused until
`bb auth logout`.

### Bitbucket Data Center / Server

1. Log in to the on-prem host, e.g. `https://bitbucket.polariswireless.com`.
2. Go to **Account settings -> HTTP access tokens**.
3. Create a token with repository and pull-request permissions.
4. Copy the token immediately.
5. Store it:

```bash
bb config set base_url https://bitbucket.polariswireless.com
bb auth login
bb doctor --json
```

## Common failures

| Symptom | Cause | Resolution |
|---|---|---|
| `bb: not authenticated — run 'bb auth login' or set BB_TOKEN` | No credentials configured | `bb auth login` or set `BB_TOKEN` env var |
| `bb: API 401: ...` | Token expired or revoked | Rotate token; `bb auth logout && bb auth login` |
| `bb: API 401: ... wrong auth type` | Data Center token stored as Basic or Cloud token used on-prem | Re-login with a fresh Data Center HTTP access token |
| `bb: API 404: ...` on `bb issue list` | Issue tracker disabled for repo | Enable it in Bitbucket repo settings → Issue tracker |
| `bb: not inside a git repo with an origin remote` | Not in a Bitbucket-hosted git repo | Pass `-R workspace/slug` or `export BB_REPO=workspace/slug` |
| `bb: API 404: ...` on `bb repo ...` | Repo slug or workspace wrong | Verify with `bb repo list --workspace myworkspace` |
| Pipeline UUID error | UUID format issue | Pass the UUID string as-is without braces |
| `bb: invalid repo ...; expected workspace/slug` | `BB_REPO` or `--repo` malformed | Use `workspace/slug` format, e.g. `myteam/myrepo` |

## Credential rotation

```bash
bb auth logout
bb auth login
# or rotate in .env / CI secrets without touching hosts.toml:
export BB_TOKEN=${NEW_TOKEN}
```

## Config management

```bash
# Show a config value:
bb config get git_protocol

# Set clone protocol to ssh:
bb config set git_protocol ssh

# Set a default workspace:
bb config set default_workspace myworkspace

# Set default repo for a project (writes bb.toml at git root):
bb repo set-default myworkspace/myrepo
```

User config file location:
- Linux: `~/.config/bb/config.toml`
- macOS: `~/Library/Application Support/bb/config.toml`

Token store:
- Preferred: OS keyring service `bb` (macOS Keychain, Linux Secret Service, Windows Credential Locker)
- Fallback file (mode 0600):
  - Linux: `~/.config/bb/hosts.toml`
  - macOS: `~/Library/Application Support/bb/hosts.toml`

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
