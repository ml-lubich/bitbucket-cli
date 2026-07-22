"""bb — Bitbucket CLI. Version is derived from installed package metadata so it
can never drift from pyproject.toml."""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("bitbucket-client")
except PackageNotFoundError:  # running from a source tree with no install metadata
    __version__ = "0.3.0"
