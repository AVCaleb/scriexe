import pytest
from exeg.corpus import Verse
from exeg.usfm import parse_usfm

SAMPLE = r"""\id 1PE ebible.org
\h 1 Peter
\toc1 Peter's First Letter
\mt1 Peter's First Letter
\c 3
\s1 A heading to be skipped
\p
\v 18 Because Christ also suffered for sins once,\f + \fr 3:18 \ft Some manuscripts read.\f* the just for the unjust,
\q1 that he might bring you to God,
\v 19 in whom he also went and preached to the spirits in prison,
\c 4
\p
\v 1 Therefore, since Christ suffered \add for us\add* in the flesh, arm yourselves.
\v 2 He uses \w grace|strong="G5485"\w* daily.
"""

def test_parse_basic():
    code, verses = parse_usfm(SAMPLE)
    assert code == "1PE"
    assert verses[0] == Verse(3, 18, "Because Christ also suffered for sins once, the just for the unjust, that he might bring you to God,")
    assert verses[1] == Verse(3, 19, "in whom he also went and preached to the spirits in prison,")
    assert verses[2].chapter == 4 and verses[2].verse == 1
    assert "for us" in verses[2].text and "\\add" not in verses[2].text

def test_word_markup_keeps_text_drops_strongs():
    _, verses = parse_usfm(SAMPLE)
    assert verses[3].text == "He uses grace daily."

def test_bridged_verse_number():
    code, verses = parse_usfm("\\id OBA\n\\c 1\n\\v 1-2 Bridged text here.\n")
    assert verses == [Verse(1, 1, "Bridged text here.")]

def test_missing_id_raises():
    with pytest.raises(ValueError):
        parse_usfm("\\c 1\n\\v 1 no id line\n")
