from exeg import corpus
from exeg.corpus import Verse, Word
from exeg.refs import parse_ref

def test_root_uses_env(corpus_root):
    assert corpus.root() == corpus_root

def test_verse_roundtrip_and_range(corpus_root):
    vv = [Verse(3, v, f"text {v}") for v in range(16, 23)] + [Verse(4, 1, "next")]
    corpus.write_verses("web", "1Pet", vv)
    assert corpus.read_verses("web", "1Pet") == vv
    got = corpus.get_verses("web", parse_ref("1Pet 3:18-22"))
    assert [v.verse for v in got] == [18, 19, 20, 21, 22]
    assert corpus.get_verses("web", parse_ref("1Pet 3")) == vv[:-1]

def test_word_roundtrip_and_join(corpus_root):
    ww = [
        Word(3, 18, 1, "ὅτι", "ὅτι", "G3754", "C-/--------"),
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
    ]
    corpus.write_words("sblgnt", "1Pet", ww)
    assert corpus.read_words("sblgnt", "1Pet") == ww
    got = corpus.get_verses("sblgnt", parse_ref("1Pet 3:18"))
    assert got == [Verse(3, 18, "ὅτι Χριστὸς")]

def test_hebrew_segment_slash_stripped(corpus_root):
    ww = [Word(1, 1, 1, "בְּ/רֵאשִׁ֖ית", "b/7225", "H7225", "HR/Ncfsa")]
    corpus.write_words("wlc", "Gen", ww)
    assert corpus.get_verses("wlc", parse_ref("Gen 1:1"))[0].text == "בְּרֵאשִׁ֖ית"

def test_missing_book_returns_empty(corpus_root):
    assert corpus.get_verses("web", parse_ref("Jude 1:1")) == []
    assert not corpus.has_version("nasb95")

def test_get_words_range(corpus_root):
    ww = [Word(3, v, 1, f"w{v}", f"l{v}", "", "N-/----NSM-") for v in (17, 18, 19)]
    corpus.write_words("sblgnt", "1Pet", ww)
    got = corpus.get_words(parse_ref("1Pet 3:18-19"), "sblgnt")
    assert [w.verse for w in got] == [18, 19]
