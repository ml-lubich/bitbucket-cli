# Plan: `bb` — lightweight Bitbucket Cloud CLI (gh-style)

Version 0.1.0 · 2026-06-11 · Python 3.12 + uv + typer + httpx

## Architecture
- `src/bb/cli.py` — typer root app; registers command groups via dict dispatch.
- `src/bb/core/` — `config.py` (layering: CLI args > env `BB_TOKEN`/`BITBUCKET_TOKEN`/`BITBUCKET_AUTH_TOKEN`/`BB_REPO` (incl. repo-local `.env`, value never read or echoed by tooling) > project `bb.toml` > user config via platformdirs > defaults), `auth.py` (token store `hosts.toml`, 0600), `client.py` (httpx wrapper, Bitbucket Cloud API 2.0, Bearer + app-password Basic), `context.py` (workspace/repo from git remote), `output.py` (table/json rendering, `--json` flag).
- `src/bb/commands/` — one module per group: `auth`, `pr`, `repo`, `issue`, `pipeline`, `branch`, `workspace`, `project`, `snippet`, `api`, `config_cmd`, `browse`. Each exposes `app: typer.Typer`.
- `tests/` — pytest, httpx MockTransport; real file writes for config/auth tests.
- Docs: 5 canonical under `docs/`; `VERSION`; `scripts/setup.sh`.

## Delegation (Sonnet subagents, parallel after core)
1. core (config/auth/client/context/output) → then in parallel:
2. pr + branch · 3. repo + workspace + project · 4. issue + pipeline + snippet · 5. auth/api/config/browse/completion + tests · 6. docs/README/setup.sh
Owner (Fable 5) integrates + runs the gate.

## Will NOT Change
- No Bitbucket Server/DC support (Cloud API 2.0 only).
- No OAuth browser flow in v0.1 (token paste only).
- No interactive TUI prompts beyond simple confirms.
- Config format is TOML (rule 109), not YAML as in gh.

## Drift Risks
- Bitbucket issue tracker is per-repo opt-in → commands must surface a clear API error, not crash.
- Pipelines UUID quoting (`{uuid}`) in URLs.
- Scope creep into snippets/projects edge cases — keep CRUD minimal.

## Verification Plan
- `uv run pytest` green (coverage ≥ 80% on `src/bb/core` + commands).
- Smoke: `uv run bb --help`, `uv run bb auth status` (no token → clean message, exit 1).
- Completion gate: exit 0 before declaring done.
