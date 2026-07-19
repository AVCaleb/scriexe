import pytest
from exeg.refs import BadRef, parse_ref

def test_basic_range():
    r = parse_ref("1Pet 3:18-22")
    assert (r.book.osis, r.chapter, r.verse, r.end_chapter, r.end_verse) == ("1Pet", 3, 18, 3, 22)

def test_spaced_name_and_en_dash():
    r = parse_ref("1 Peter 3:18–22")
    assert r.book.osis == "1Pet" and r.end_verse == 22

def test_chinese_ref_fullwidth_colon():
    r = parse_ref("彼前3：18-22")
    assert r.book.osis == "1Pet" and (r.chapter, r.verse, r.end_verse) == (3, 18, 22)

def test_single_verse():
    r = parse_ref("John 11:35")
    assert (r.chapter, r.verse, r.end_chapter, r.end_verse) == (11, 35, 11, 35)

def test_whole_chapter():
    r = parse_ref("诗 23")
    assert r.book.osis == "Ps" and r.chapter == 23 and r.verse is None

def test_cross_chapter():
    r = parse_ref("Gen 1:28-2:3")
    assert (r.chapter, r.verse, r.end_chapter, r.end_verse) == (1, 28, 2, 3)

def test_labels_and_slug():
    r = parse_ref("1Pet 3:18-22")
    assert r.en_label() == "1 Peter 3:18–22"
    assert r.zh_label() == "彼前 3:18–22"
    assert r.zh_label(full=True) == "彼得前书 3:18–22"
    assert r.slug() == "1pet_3.18-22"
    assert parse_ref("Ps 23").slug() == "ps_23"
    assert parse_ref("Gen 1:28-2:3").slug() == "gen_1.28-2.3"

def test_contains():
    r = parse_ref("Gen 1:28-2:3")
    assert r.contains(1, 30) and r.contains(2, 3) and not r.contains(2, 4)
    c = parse_ref("Ps 23")
    assert c.contains(23, 6) and not c.contains(24, 1)

def test_chapter_out_of_range():
    with pytest.raises(BadRef):
        parse_ref("1Pet 6:1")

def test_mt_versification_allowed():
    parse_ref("Joel 4:1")     # MT has 4 chapters

def test_backwards_range_rejected():
    with pytest.raises(BadRef):
        parse_ref("1Pet 3:22-18")

def test_garbage_rejected():
    with pytest.raises(BadRef):
        parse_ref("hello world")
