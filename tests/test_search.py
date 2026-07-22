import json
from exeg import corpus, search
from exeg.corpus import Verse, Word

def seed(corpus_root):
    corpus.write_verses("web", "1Pet", [
        Verse(1, 3, "has begotten us again to a living hope"),
        Verse(2, 24, "who his own self bore our sins"),
    ])
    corpus.write_words("sblgnt", "1Pet", [
        Word(2, 21, 1, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 18, 1, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
    ])
    sdir = corpus.corpus_dir() / "strongs"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "greek.json").write_text(json.dumps(
        {"G3958": {"lemma": "πάσχω", "strongs_def": "to experience a sensation, suffer"}}), encoding="utf-8")
    (sdir / "greek-lemma-map.json").write_text(json.dumps({"πάσχω": "G3958"}), encoding="utf-8")
    (sdir / "hebrew.json").write_text("{}", encoding="utf-8")

def test_search_text(corpus_root):
    seed(corpus_root)
    hits = search.search_text("living hope", ["web"])
    assert hits == [("web", "1Pet", 1, 3, "has begotten us again to a living hope")]

def test_search_original_language_surface_text(corpus_root):
    seed(corpus_root)
    hits = search.search_text("Χριστ", ["sblgnt"])
    assert hits == [("sblgnt", "1Pet", 3, 18, "ἔπαθεν Χριστὸς")]


def test_search_lemma(corpus_root):
    seed(corpus_root)
    hits = search.search_text("πάσχω", ["sblgnt"], lemma=True)
    assert [(h[2], h[3]) for h in hits] == [(2, 21), (3, 18)]

def test_word_by_strongs_and_lemma(corpus_root):
    seed(corpus_root)
    for q in ("G3958", "g3958", "πάσχω"):
        r = search.word_occurrences(q)
        assert r["strongs"] == "G3958" and r["lemma"] == "πάσχω"
        assert "suffer" in r["gloss"]
        assert r["by_book"] == {"1Pet": 2}

def test_morph_label():
    assert search.greek_morph_label("V-/3AAI-S--") == "aorist active indicative 3sg"
    assert search.greek_morph_label("N-/----NSF-") == "nom sg f"
    assert search.greek_morph_label("HVqp3ms") == "HVqp3ms"   # Hebrew stays raw

def test_word_by_strongs_does_not_widen_to_shared_lemma(corpus_root):
    seed(corpus_root)
    corpus.write_words("wlc", "Gen", [
        Word(1, 1, 1, "ברא", "1254 a", "H1254", "HVqp3ms"),
        Word(1, 2, 1, "ברא", "1254 a", "H1255", "HVqp3ms"),
    ])
    r = search.word_occurrences("H1254")
    assert r["by_book"] == {"Gen": 1}
    assert r["lemma"] == "1254 a"

def test_cli(corpus_root, capsys):
    seed(corpus_root)
    from exeg.cli import main
    assert main(["search", "living hope", "--versions", "web"]) == 0
    assert "1Pet 1:3" in capsys.readouterr().out
    assert main(["word", "G3958"]) == 0
    out = capsys.readouterr().out
    assert "πάσχω" in out and "2×" in out

def test_cli_search_unknown_book(corpus_root, capsys):
    from exeg.cli import main
    assert main(["search", "x", "--book", "zzz"]) == 1
    assert "Unknown book" in capsys.readouterr().err

def test_cli_search_bad_pattern(corpus_root, capsys):
    from exeg.cli import main
    assert main(["search", "("]) == 1
    assert "bad pattern" in capsys.readouterr().err
