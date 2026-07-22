import pytest
from exeg import corpus, importer
from exeg.refs import parse_ref

def test_import_tsv(corpus_root, tmp_path):
    src = tmp_path / "nasb.tsv"
    src.write_text("1Pet 3:18\tFor Christ also died for sins once for all\n"
                   "1Pet 3:19\tin which also He went\n"
                   "彼前 4:1\tmixed-ref-style line\n", encoding="utf-8")
    n = importer.import_path(src, "nasb95", log=lambda *a: None)
    assert n == 1
    got = corpus.get_verses("nasb95", parse_ref("1Pet 3:18-19"))
    assert [v.verse for v in got] == [18, 19]
    assert corpus.get_verses("nasb95", parse_ref("1Pet 4:1"))[0].text == "mixed-ref-style line"

def test_import_usfm_dir(corpus_root, tmp_path):
    d = tmp_path / "mod"
    d.mkdir()
    (d / "1pe.usfm").write_text("\\id 1PE\n\\c 3\n\\v 18 For Christ also died.\n", encoding="utf-8")
    (d / "jud.usfm").write_text("\\id JUD\n\\c 1\n\\v 1 Jude, a bond-servant.\n", encoding="utf-8")
    n = importer.import_path(d, "nasb95", log=lambda *a: None)
    assert n == 2
    assert corpus.has_book("nasb95", "Jude")

def test_bad_tsv_line_reported(corpus_root, tmp_path):
    src = tmp_path / "bad.tsv"
    src.write_text("not a reference\tsome text\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        importer.import_path(src, "nasb95", log=lambda *a: None)

def test_cli_import(corpus_root, tmp_path, capsys):
    src = tmp_path / "n.tsv"
    src.write_text("John 11:35\tJesus wept.\n", encoding="utf-8")
    from exeg.cli import main
    assert main(["import", str(src), "--version", "nasb95"]) == 0
    assert corpus.has_version("nasb95")


def test_import_tsv_version_from_header(corpus_root, tmp_path):
    src = tmp_path / "my.tsv"
    src.write_text("# version: myver\n"
                   "# just a comment\n"
                   "Gen 1:1\tIn the beginning God created.\n"
                   "Gen 1:2\tAnd the earth was formless.\n", encoding="utf-8")
    n = importer.import_path(src, None, log=lambda *a: None)
    assert n == 1
    assert corpus.has_version("myver")
    assert corpus.read_verses("myver", "Gen")[0].text.startswith("In the beginning")


def test_import_tsv_skips_comments_and_blank(corpus_root, tmp_path):
    src = tmp_path / "c.tsv"
    src.write_text("# header comment\n\n"
                   "Ps 23:1\tThe LORD is my shepherd.\n", encoding="utf-8")
    n = importer.import_path(src, "psonly", log=lambda *a: None)
    assert n == 1
    assert corpus.read_verses("psonly", "Ps")[0].text == "The LORD is my shepherd."


def test_import_no_version_raises(corpus_root, tmp_path):
    src = tmp_path / "nv.tsv"
    src.write_text("Gen 1:1\ttext\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        importer.import_path(src, None, log=lambda *a: None)


def test_import_example_flag(capsys):
    from exeg.cli import main
    assert main(["import", "--example"]) == 0
    out = capsys.readouterr().out
    assert "REFERENCE<TAB>" in out or "REF<TAB>" in out or "# version:" in out
    assert "1Pet 3:18" in out


def test_shipped_example_file_parses(corpus_root):
    # the repo's examples/import-sample.tsv should import cleanly
    from pathlib import Path
    sample = Path(__file__).resolve().parents[1] / "examples" / "import-sample.tsv"
    assert sample.exists()
    n = importer.import_path(sample, None, log=lambda *a: None)
    assert n >= 2  # Gen + Ps + 1Pet
    assert corpus.has_version("import-sample")
    assert corpus.read_verses("import-sample", "Gen")[0].text.startswith("In the beginning")
