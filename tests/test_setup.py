"""Tests for the onboarding/setup wizard (exeg.setup)."""
import os

import pytest

from exeg import setup as _setup


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(_setup, "env_path", lambda: tmp_path / ".env")
    return tmp_path / ".env"


def test_write_env_key_creates_and_replaces(tmp_env):
    _setup.write_env_key("ESV_API_KEY", "abc")
    assert tmp_env.read_text().strip() == "ESV_API_KEY=abc"
    _setup.write_env_key("ESV_API_KEY", "def")
    assert tmp_env.read_text().strip() == "ESV_API_KEY=def"


def test_write_env_key_creates_user_root(tmp_path, monkeypatch):
    nested = tmp_path / "new-user-root" / ".env"
    monkeypatch.setattr(_setup, "env_path", lambda: nested)
    _setup.write_env_key("ESV_API_KEY", "abc")
    assert nested.read_text(encoding="utf-8").strip() == "ESV_API_KEY=abc"


def test_write_env_key_blank_deletes(tmp_env):
    _setup.write_env_key("ESV_API_KEY", "abc")
    _setup.write_env_key("ESV_API_KEY", "")
    assert not tmp_env.exists() or tmp_env.read_text().strip() == ""


def test_write_env_key_preserves_other_keys(tmp_env):
    _setup.write_env_key("FOO", "1")
    _setup.write_env_key("ESV_API_KEY", "abc")
    _setup.write_env_key("ESV_API_KEY", "xyz")
    text = tmp_env.read_text()
    assert "FOO=1" in text
    assert "ESV_API_KEY=xyz" in text
    assert "abc" not in text


def test_key_is_set_reads_env_and_file(tmp_env, monkeypatch):
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    assert _setup.key_is_set("ESV_API_KEY") is False
    _setup.write_env_key("ESV_API_KEY", "abc")
    assert _setup.key_is_set("ESV_API_KEY") is True
    monkeypatch.setenv("API_BIBLE_KEY", "live")
    _setup.write_env_key("API_BIBLE_KEY", "")
    assert _setup.key_is_set("API_BIBLE_KEY") is True  # via environ


def test_run_setup_writes_keys_and_meta(tmp_env, tmp_path, monkeypatch):
    import exeg.notes as notes
    monkeypatch.setattr(notes, "notes_root", lambda: tmp_path / "notes")
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    monkeypatch.delenv("API_BIBLE_KEY", raising=False)
    monkeypatch.setattr(_setup.getpass, "getpass",
                        lambda prompt="": "SECRET-ESV" if "ESV" in prompt else "SECRET-NASB")
    answers = iter(["zh", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    cfg = _setup.run_setup()
    assert cfg["lang"] == "zh"
    assert cfg.get("esv") is True
    assert cfg.get("nasb") is True
    assert "ESV_API_KEY=SECRET-ESV" in tmp_env.read_text()
    assert os.environ.get("ESV_API_KEY") == "SECRET-ESV"
    m = notes.read_meta()
    assert m.get("setup_done") is True
    assert m.get("lang") == "zh"


def test_run_setup_keys_optional_default_skip(tmp_env, tmp_path, monkeypatch):
    """Answering anything but 'y' to the gate skips the whole key section."""
    import exeg.notes as notes
    monkeypatch.setattr(notes, "notes_root", lambda: tmp_path / "notes")
    # gate answered with empty (default N)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    monkeypatch.setattr(_setup.getpass, "getpass",
                        lambda prompt="": pytest.fail("keys should not be asked"))
    cfg = _setup.run_setup()
    assert cfg.get("esv") is None and cfg.get("nasb") is None
    assert not tmp_env.exists() or "ESV_API_KEY" not in tmp_env.read_text()


def test_is_configured_reflects_meta(tmp_path, monkeypatch):
    import exeg.notes as notes
    monkeypatch.setattr(notes, "notes_root", lambda: tmp_path / "notes")
    assert _setup.is_configured() is False
    notes.write_meta({"setup_done": True})
    assert _setup.is_configured() is True