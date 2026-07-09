from __future__ import annotations

import bb.core.config as cfg_mod
from bb.core.config import Settings, load_settings


def test_defaults_return_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BB_GIT_PROTOCOL", raising=False)
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    s = load_settings()
    assert s.git_protocol == "https"


def test_env_git_protocol_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("BB_GIT_PROTOCOL", "ssh")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    s = load_settings()
    assert s.git_protocol == "ssh"


def test_env_editor_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("BB_EDITOR", "vim")
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    s = load_settings()
    assert s.editor == "vim"


def test_proj_cfg_overrides_user_cfg(monkeypatch, tmp_path):
    user_cfg = tmp_path / "config.toml"
    user_cfg.write_text('git_protocol = "ssh"\n')
    proj_cfg = tmp_path / "bb.toml"
    proj_cfg.write_text('git_protocol = "https"\n')
    monkeypatch.delenv("BB_GIT_PROTOCOL", raising=False)
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: user_cfg)
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: proj_cfg)
    s = load_settings()
    assert s.git_protocol == "https"


def test_user_cfg_persisted(monkeypatch, tmp_path):
    user_cfg = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: user_cfg)
    cfg_mod.set_value("editor", "nano")
    assert "nano" in user_cfg.read_text()


def test_get_value_returns_string(monkeypatch, tmp_path):
    user_cfg = tmp_path / "config.toml"
    user_cfg.write_text('editor = "emacs"\n')
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: user_cfg)
    result = cfg_mod.get_value("editor")
    assert result == "emacs"


def test_missing_user_cfg_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "nonexistent.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    s = load_settings()
    assert isinstance(s, Settings)


def test_env_base_url_normalized(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "BB_BASE_URL",
        "https://bitbucket.polariswireless.com/plugins/servlet/access-tokens/users/mlubich/manage",
    )
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cfg_mod, "_proj_cfg_path", lambda: tmp_path / "bb.toml")
    assert load_settings().base_url == "https://bitbucket.polariswireless.com"


def test_set_base_url_normalizes(monkeypatch, tmp_path):
    user_cfg = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_mod, "_user_cfg_path", lambda: user_cfg)
    cfg_mod.set_value("base_url", "bitbucket.polariswireless.com")
    assert cfg_mod.get_value("base_url") == "https://bitbucket.polariswireless.com"
