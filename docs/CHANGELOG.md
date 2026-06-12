# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-11

### Added

- Token authentication: `bb auth login --token`, `bb auth logout`, `bb auth status`.
  - Token sources (priority order): `BB_TOKEN` env > `BITBUCKET_TOKEN` env > `BITBUCKET_AUTH_TOKEN` env > repo-local `.env` > `hosts.toml` (mode 0600, platformdirs).
  - Credentials never echoed; `masked()` used for any display reference.
- Pull request commands: `pr list`, `pr view`, `pr create`, `pr checkout`, `pr merge`, `pr close`, `pr edit`, `pr review`, `pr comment`, `pr diff`, `pr checks`.
  - `pr reopen` surfaces a documented error (Bitbucket Cloud API has no reopen endpoint).
- Repository commands: `repo list`, `repo view`, `repo clone`, `repo create`, `repo fork`, `repo delete`, `repo sync`, `repo set-default`.
  - Clone respects `git_protocol` config key (`https` or `ssh`).
- Issue tracker commands: `issue list`, `issue view`, `issue create`, `issue edit`, `issue close`, `issue reopen`, `issue comment`, `issue delete`.
  - Clear error when issue tracker is disabled for a repo (API 404).
- Pipeline commands: `pipeline list`, `pipeline run`, `pipeline view`, `pipeline steps`, `pipeline logs`, `pipeline stop`.
- Branch commands: `branch list`, `branch create`, `branch delete`.
- Workspace commands: `workspace list`, `workspace view`, `workspace members`.
- Project commands: `project list`, `project view`, `project create`.
- Snippet commands: `snippet list`, `snippet view`, `snippet create`, `snippet edit`, `snippet delete`.
- Raw API command: `bb api <endpoint>` with `--method`, `--field`, `--input`.
- Config layering: CLI args > env > project `bb.toml` > user `config.toml` (platformdirs) > defaults.
  - Keys: `git_protocol`, `editor`, `default_workspace`.
  - `config get` and `config set` subcommands.
- Shell completion: `completion bash`, `completion zsh`, `completion fish`, `completion powershell`.
- Browse: `bb browse` opens current repo or a specific PR/issue/pipeline/branch in the system browser.
- Plain table output (rich) and `--json` flag for structured output on all list/view commands.
- Global `-R / --repo` flag to override git-remote context detection.
- `BBError` hierarchy: `AuthError`, `ApiError`, `ContextError`, `ConfigError`; single catch in `cli.main()`.
- `scripts/setup.sh`: idempotent uv-based setup for macOS and Linux.
- Five canonical docs under `docs/`: ARCHITECTURE, API, TESTING, RUNBOOK, CHANGELOG.
