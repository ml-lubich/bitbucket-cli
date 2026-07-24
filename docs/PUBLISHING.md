# Publishing

## PyPI

Build and verify locally:

```bash
./scripts/quality.sh
uv build
```

Publish with a PyPI trusted publisher or token:

```bash
uv publish
```

### Recommended: GitHub Actions (trusted publishing)

1. On PyPI → Account settings → Publishing → **Add a pending publisher**:
   - **PyPI project name:** `bitbucket-client`
   - **Owner:** `ml-lubich`
   - **Repository:** `bitbucket-cli`
   - **Workflow:** `publish.yml`
   - **Environment name:** *(leave blank)*
2. Push a release or run the workflow manually:
   - GitHub → Actions → **Publish** → **Run workflow**
   - Or publish/republish GitHub release `v0.2.0`

The workflow runs `./scripts/quality.sh`, `uv build`, then
`pypa/gh-action-pypi-publish` (OIDC — no stored PyPI token).

### Local token publish (fallback)

Requires a valid API token in `~/.pypirc` (`username = __token__`) or
`UV_PUBLISH_TOKEN`. Create at https://pypi.org/manage/account/token/
(scope: entire account or project `bitbucket-client`).

After publish, install from PyPI:

```bash
uv tool install bitbucket-client
bb --version
```

The PyPI distribution name is `bitbucket-client` (console script remains `bb`).
The GitHub repository stays `ml-lubich/bitbucket-cli`.

## Homebrew

Tap: [`ml-lubich/homebrew-tap`](https://github.com/ml-lubich/homebrew-tap)
(`brew tap ml-lubich/tap`). Formula: `Formula/bitbucket-client.rb`.

On each PyPI release:

1. Confirm sdist URL + sha256 from
   `https://pypi.org/pypi/bitbucket-client/<version>/json`.
2. Bump `url` / `sha256` in the tap formula.
3. Regenerate Python resources if deps changed:
   `brew update-python-resources ml-lubich/tap/bitbucket-client`
   (or edit `resource` blocks by hand). Keep `depends_on "rust" => :build`
   while `pydantic-core` builds from source.
4. Commit + push the tap; locally:
   `brew update && brew upgrade ml-lubich/tap/bitbucket-client && brew test bitbucket-client`

Install:

```bash
brew install ml-lubich/tap/bitbucket-client
bb --version
bb mcp serve   # read-only MCP for agents
```

Ensure `/opt/homebrew/bin/bb` links into the Cellar formula — not a repo
`venv/bin/bb` or a stale `uv tool` shim.

## Release Checklist

1. Update `src/bb/__init__.py` and `pyproject.toml` to the same version.
2. Update `docs/CHANGELOG.md`.
3. Run `./scripts/quality.sh`.
4. Build with `uv build`.
5. Publish to PyPI with `uv publish`.
6. Create a GitHub release.
7. Update the Homebrew tap formula.
