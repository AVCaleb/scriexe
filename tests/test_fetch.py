from exeg import fetch
from exeg.corpus import Word

MORPHGNT_SAMPLE = """\
610101 N- ----NSF- Βίβλος Βίβλος βίβλος βίβλος
610101 N- ----GSF- γενέσεως γενέσεως γενέσεως γένεσις
610102 V- 3AAI-S-- ἐγέννησεν ἐγέννησεν ἐγέννησεν γεννάω
"""

WLC_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">
 <osisText><div><chapter osisID="Gen.1">
  <verse osisID="Gen.1.1">
   <w lemma="b/7225" morph="HR/Ncfsa" id="01xeN">בְּ/רֵאשִׁ֖ית</w>
   <w lemma="1254 a" morph="HVqp3ms" id="01Nvk">בָּרָ֣א</w>
   <seg type="x-sof-pasuq">׃</seg>
  </verse>
 </chapter></div></osisText>
</osis>"""

STRONGS_JS = """/* header comment
with junk */
var strongsGreekDictionary = {"G1096": {"lemma": "γίνομαι", "strongs_def": "to cause to be"},
"G1080": {"lemma": "γεννάω", "strongs_def": "to procreate"}};
"""

def test_parse_strongs_js_and_lemma_map():
    d = fetch.parse_strongs_js(STRONGS_JS)
    assert d["G1080"]["lemma"] == "γεννάω"
    m = fetch.build_greek_lemma_map(d)
    assert m["γεννάω"] == "G1080"

def test_normalize_sblgnt():
    words = fetch.normalize_sblgnt(MORPHGNT_SAMPLE, {"γεννάω": "G1080"})
    assert words[0] == Word(1, 1, 1, "Βίβλος", "βίβλος", "", "N-/----NSF-")
    assert words[2] == Word(1, 2, 1, "ἐγέννησεν", "γεννάω", "G1080", "V-/3AAI-S--")

def test_normalize_wlc():
    words = fetch.normalize_wlc(WLC_SAMPLE)
    assert len(words) == 2                      # <seg> skipped
    assert words[0].surface == "בְּ/רֵאשִׁ֖ית"
    assert words[0].strongs == "H7225" and words[0].morph == "HR/Ncfsa"
    assert words[1].strongs == "H1254"

def test_integrity_reports_gap(corpus_root):
    from exeg import corpus
    corpus.write_verses("web", "Titus", [corpus.Verse(1, 1, "a"), corpus.Verse(3, 1, "c")])
    problems = fetch.check_integrity()
    assert any("Titus" in p and "web" in p for p in problems)

def test_integrity_accepts_mt_chapters(corpus_root):
    from exeg import corpus
    corpus.write_words("wlc", "Joel", [corpus.Word(c, 1, 1, "א", "1", "H1", "HNcmsa") for c in (1, 2, 3, 4)])
    assert fetch.check_integrity() == []
