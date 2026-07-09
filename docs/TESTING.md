# Testing

## Verify command

```bash
UV_PROJECT_ENVIRONMENT=venv uv run pytest
```

Full quality gate:

```bash
./scripts/quality.sh
```

With coverage:

```bash
UV_PROJECT_ENVIRONMENT=venv uv run pytest --cov=bb --cov-report=term-missing
```

Coverage target: ≥ 85% total line/branch coverage for `bb`, enforced in
`pyproject.toml`. The long-term target is 100%; raise the ratchet when coverage
improves.

## Definition of Done

A feature is not done until:

1. **Feature test** — behavior is explicitly tested and passing. Tests import
   from `src/bb` (via `pythonpath = ["src"]` in `pyproject.toml`).
2. **Smoke test** — `UV_PROJECT_ENVIRONMENT=venv uv run bb --help`,
   `UV_PROJECT_ENVIRONMENT=venv uv run bb -h`, and
   `UV_PROJECT_ENVIRONMENT=venv uv run bb help` exit 0;
   `UV_PROJECT_ENVIRONMENT=venv uv run bb auth status` with no token exits 1
   with a clean message.
3. **Side effects** — config and auth tests must use real file writes to a
   temp directory (`tmp_path` pytest fixture). Assert the written TOML content
   and file permissions (e.g. `hosts.toml` mode 0o600). Do not mock the
   filesystem.
4. **Coverage gate** — `./scripts/quality.sh`
   must pass the configured coverage threshold. Any intentionally excluded surface
   is listed under "Not tested" below.
5. **One assert per test** — use `pytest.mark.parametrize` for multiple
   states; do not stack asserts.
6. **Suite exit 0** — no skips on core behavior; no xfail without a linked
   issue.

## HTTP boundary

Mock HTTP at the `httpx.MockTransport` layer only. Pass the transport directly
to `ApiClient` via its constructor seam or to `raw_request()` via its transport
parameter. Do not monkeypatch `httpx.Client` or any other module-level symbol.

```python
transport = httpx.MockTransport(handler)
client = ApiClient(cred=some_cred, transport=transport)
```

The `handler` callable receives an `httpx.Request` and returns an
`httpx.Response`.

## Auth and config tests

- Write to a real temp directory (`tmp_path` fixture).
- Assert `hosts.toml` exists with mode `0o600`.
- Assert TOML content by parsing with `tomlkit`, not string matching.
- Never pass a raw token string to an assertion that compares against output;
  use `masked()` from `core/output.py` or check the file directly.

## Test naming

Name tests by the behavior they protect, not the function they call.

Good: `test_auth_status_exits_1_when_no_token`
Bad: `test_load_credentials`

## HTTPS git auth

`bb repo clone`, `repo sync`, and `pr checkout` must inject the active
credential into git HTTPS operations. Cover with:

- Unit: `authorization_header` / `git_command` in `tests/test_auth.py`
  (Bearer and Basic)
- Command: `tests/test_repo_extended.py` asserts `git -c http.extraHeader=…`
  on HTTPS clone/sync and no header on SSH clone
- Command: `tests/test_pr_extended_cmd.py` asserts the same header on
  `pr checkout` fetch

## Data Center workspace / project slug

DC projects expose `key`, not Cloud `slug`. Client normalization must set
`slug` from `key` for `/workspaces` and `/workspaces/{key}` responses.
Cover this with:

- Unit: `_normalize_datacenter_response("/workspaces", ...)` asserts `slug`
- Integration: `ApiClient.paginate("/workspaces")` against `MockTransport`
  returning DC project payloads; assert path `/rest/api/1.0/projects` and
  non-empty `slug` values
- Command: `bb workspace list` with a key-only fixture still prints the key
  in the SLUG column

## Not tested (intentional)

- **Live Bitbucket API** — no integration tests against real endpoints;
  `httpx.MockTransport` covers all HTTP scenarios, including raw text
  requests.
- **Browser opening** — `webbrowser.open` is monkeypatched in `browse` tests;
  the actual OS browser call is not asserted to fire.
- **Live OS keyring** — tests use an in-memory keyring stub (autouse fixture
  disables the real backend); `tests/test_keyring.py` covers set/get/delete.
- **Auth TDD matrix** — `tests/test_auth_matrix.py` generates ≥5000 parametrized
  cases (precedence, keyring/file round-trip, host isolation, CLI login/logout,
  masking). Run with:
  `UV_PROJECT_ENVIRONMENT=venv uv run pytest tests/test_auth_matrix.py -q`
- **Shell completion sourcing** — completion output is string-tested;
  sourcing into a live shell is not automated.
- **Windows paths** — `platformdirs` behavior on Windows is not tested;
  supported platforms are macOS and Linux (matching `scripts/setup.sh`).
