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
