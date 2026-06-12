"""Tests for token resolution precedence in bb.core.auth."""
from __future__ import annotations

import pytest


def test_bb_token_beats_bitbucket_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "bb-tok")
    monkeypatch.setenv("BITBUCKET_TOKEN", "other-tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "bb-tok"


def test_bitbucket_token_used_when_no_bb_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_TOKEN", "bt-tok")
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    monkeypatch.setattr("bb.core.auth._denv_token", lambda: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "bt-tok"


def test_auth_token_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.setenv("BITBUCKET_AUTH_TOKEN", "auth-tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    monkeypatch.setattr("bb.core.auth._denv_token", lambda: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "auth-tok"


def test_dotenv_fallback_reads_file(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    from pathlib import Path
    dotenv = Path(str(tmp_path)) / ".env"
    dotenv.write_text("BB_TOKEN=dotenv-tok
")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BB_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert cred.token == "dotenv-tok"


def test_source_reflects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_TOKEN", "tok")
    monkeypatch.setattr("bb.core.auth._cred_from_file", lambda *_: None)
    from bb.core.auth import resolve_credential
    cred = resolve_credential()
    assert "BB_TOKEN" in cred.source
