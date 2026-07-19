import pytest
from exeg.canon import BOOKS, BY_OSIS, NT_BOOKS, USFM_TO_OSIS, UnknownBook, find_book, max_chapters

def test_table_shape():
    assert len(BOOKS) == 66
    assert len(NT_BOOKS) == 27
    assert NT_BOOKS[0].osis == "Matt" and NT_BOOKS[-1].osis == "Rev"
    assert BY_OSIS["1Pet"].zh == "彼得前书" and BY_OSIS["1Pet"].chapters == 5
    assert USFM_TO_OSIS["1PE"] == "1Pet"

def test_find_book_english_forms():
    for q in ("1Pet", "1 Peter", "1peter", "1PE", "1pe", "gen", "Genesis", "song", "Ps", "mt", "jn"):
        find_book(q)
    assert find_book("1 Peter").osis == "1Pet"
    assert find_book("mt").osis == "Matt"
    assert find_book("ex").osis == "Exod"

def test_find_book_chinese_forms():
    assert find_book("彼前").osis == "1Pet"
    assert find_book("彼得前书").osis == "1Pet"
    assert find_book("创").osis == "Gen"
    assert find_book("启").osis == "Rev"

def test_ambiguous_prefix_raises_with_suggestions():
    with pytest.raises(UnknownBook) as e:
        find_book("ju")          # Judges vs Jude
    assert {"Judg", "Jude"} <= set(e.value.suggestions)

def test_unknown_book_suggests_close_match():
    with pytest.raises(UnknownBook) as e:
        find_book("Filippians")
    assert "Phil" in e.value.suggestions

def test_mt_chapter_overrides():
    assert max_chapters(BY_OSIS["Joel"]) == 4
    assert max_chapters(BY_OSIS["Mal"]) == 4   # max(en 4, MT 3)
    assert max_chapters(BY_OSIS["Gen"]) == 50
