from exeg import corpus, display
from exeg.corpus import Verse, Word
from exeg.refs import parse_ref

def seed(corpus_root):
    corpus.write_words("sblgnt", "1Pet", [
        Word(3, 18, 1, "ὅτι", "ὅτι", "G3754", "C-/--------"),
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
        Word(3, 19, 1, "ἐν", "ἐν", "G1722", "P-/--------"),
    ])
    corpus.write_verses("cuvs", "1Pet", [Verse(3, 18, "因基督也曾一次为罪受苦"), Verse(3, 19, "他借这灵曾去传道")])
    corpus.write_verses("web", "1Pet", [Verse(3, 18, "Because Christ also suffered for sins once")])

def test_render_parallel(corpus_root):
    seed(corpus_root)
    out = display.render(parse_ref("1Pet 3:18-19"), ["sblgnt", "web", "cuvs"])
    assert "### 1 Peter 3:18 · 彼前 3:18" in out
    assert "- **SBLGNT** ὅτι Χριστὸς" in out
    assert "- **和合本** 因基督也曾一次为罪受苦" in out
    # web lacks v19 -> explicit marker, not silent skip
    assert "- **WEB** [not in WEB]" in out

def test_unavailable_api_version_noted(corpus_root):
    seed(corpus_root)
    out = display.render(parse_ref("1Pet 3:18"), ["esv", "cuvs"])
    assert "> ESV unavailable" in out
    assert "- **和合本**" in out

def test_default_versions(corpus_root):
    from exeg.canon import BY_OSIS
    assert display.default_versions(BY_OSIS["1Pet"])[0] == "sblgnt"
    assert display.default_versions(BY_OSIS["Gen"])[0] == "wlc"

def test_cli_passage(corpus_root, capsys):
    seed(corpus_root)
    from exeg.cli import main
    assert main(["passage", "彼前3:18", "--versions", "sblgnt,cuvs"]) == 0
    out = capsys.readouterr().out
    assert "ὅτι Χριστὸς" in out and "因基督" in out

def test_cli_bad_ref_message(corpus_root, capsys):
    from exeg.cli import main
    assert main(["passage", "Filippians 1:1"]) == 1
    assert "Did you mean" in capsys.readouterr().err

def test_local_import_checked_per_book(corpus_root, monkeypatch):
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    monkeypatch.delenv("API_BIBLE_KEY", raising=False)
    corpus.write_verses("nasb95", "1Pet", [Verse(3, 18, "local nasb text")])
    out = display.render(parse_ref("1Pet 3:18"), ["nasb95"])
    assert "local nasb text" in out
    out2 = display.render(parse_ref("John 11:35"), ["nasb95"])
    assert "> NASB95 unavailable" in out2
    assert "[not in NASB95]" not in out2
