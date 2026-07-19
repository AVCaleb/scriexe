import pytest

@pytest.fixture
def corpus_root(tmp_path, monkeypatch):
    monkeypatch.setenv("EXEG_ROOT", str(tmp_path))
    return tmp_path
