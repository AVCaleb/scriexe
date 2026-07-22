import subprocess
import sys
from pathlib import Path

from exeg import canon


ROOT = Path(__file__).resolve().parents[1]


def test_core_staging_copies_only_cuvs_and_asv(tmp_path):
    source = tmp_path / "source"
    for version in ("cuvs", "asv"):
        d = source / "data" / "corpus" / version
        d.mkdir(parents=True)
        for book in canon.BOOKS:
            (d / f"{book.osis}.tsv").write_text("1\t1\ttest\n", encoding="utf-8")
    forbidden = source / "data" / "corpus" / "nasb95"
    forbidden.mkdir(parents=True)
    (forbidden / "Gen.tsv").write_text("licensed", encoding="utf-8")
    out = tmp_path / "core"
    subprocess.run([sys.executable, str(ROOT / "packaging" / "build_core_data.py"),
                    "--source-root", str(source), "--output", str(out)], check=True)
    assert {p.name for p in (out / "data" / "corpus").iterdir()} == {"cuvs", "asv"}
    assert len(list((out / "data" / "corpus" / "cuvs").glob("*.tsv"))) == 66
    assert not (out / "data" / "corpus" / "nasb95").exists()


def test_project_exposes_scriexe_and_distribution_extra():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'scriexe = "exeg.cli:main"' in text
    assert "pyinstaller" in text.lower()
    assert "windows-curses" in text.lower()


def test_pyinstaller_spec_resolves_repository_from_spec_directory():
    text = (ROOT / "packaging" / "scriexe.spec").read_text(encoding="utf-8")
    assert "root = Path(SPECPATH).parent\n" in text
    assert "Path(SPECPATH).parent.parent" not in text


def test_release_workflow_declares_all_targets():
    text = (ROOT / ".github" / "workflows" / "release-scriexe.yml").read_text(encoding="utf-8")
    for target in ("darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64", "win32-x64"):
        assert target in text
    assert "build_core_data.py" in text
    assert "pyinstaller" in text.lower()
    assert "NPM_TOKEN" in text
