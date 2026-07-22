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
   - **PyPI project name:** `bbctl`
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
(scope: entire account or project `bbctl`).

After publish, install from PyPI:

```bash
uv tool install bbctl
bb --version
```

The PyPI distribution name is `bbctl` (console script remains `bb`).
The GitHub repository stays `ml-lubich/bitbucket-cli`.

## Homebrew

Recommended shape:

1. Publish a GitHub release with an sdist tarball.
2. Compute the tarball SHA256.
3. Update a tap formula with the new version and SHA.

Example formula:

```ruby
class BitbucketCli < Formula
  include Language::Python::Virtualenv

  desc "Minimal gh-style CLI for Bitbucket Cloud and Data Center"
  homepage "https://github.com/ml-lubich/bitbucket-cli"
  url "https://files.pythonhosted.org/packages/source/b/bbctl/bbctl-0.3.0.tar.gz"
  sha256 "REPLACE_WITH_SDIST_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "bb version", shell_output("#{bin}/bb --version")
  end
end
```

Install from a tap after the formula is pushed:

```bash
brew tap ml-lubich/tap
brew install bbctl
```

## Release Checklist

1. Update `src/bb/__init__.py` and `pyproject.toml` to the same version.
2. Update `docs/CHANGELOG.md`.
3. Run `./scripts/quality.sh`.
4. Build with `uv build`.
5. Publish to PyPI with `uv publish`.
6. Create a GitHub release.
7. Update the Homebrew tap formula.
