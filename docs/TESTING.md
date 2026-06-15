# Testing

## Verify command

```bash
UV_PROJECT_ENVIRONMENT=venv uv run pytest
```

With coverage:

```bash
UV_PROJECT_ENVIRONMENT=venv uv run pytest --cov=bb --cov-report=term-missing
```

Coverage target: ≥ 80% statements, lines, functions, and branches for
`src/bb/core/` and `src/bb/commands/`.

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
4. **Coverage gate** — `UV_PROJECT_ENVIRONMENT=venv uv run pytest --cov=bb`
   must report ≥ 80% for the covered scope. Any intentionally excluded surface
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

## Not tested (intentional)

- **Live Bitbucket API** — no integration tests against real endpoints;
  `httpx.MockTransport` covers all HTTP scenarios, including raw text
  requests.
- **Browser opening** — `webbrowser.open` is monkeypatched in `browse` tests;
  the actual OS browser call is not asserted to fire.
- **Shell completion sourcing** — completion output is string-tested;
  sourcing into a live shell is not automated.
- **Windows paths** — `platformdirs` behavior on Windows is not tested;
  supported platforms are macOS and Linux (matching `scripts/setup.sh`).
