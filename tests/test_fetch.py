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


def test_normalize_usfx_minimal():
    from exeg import fetch
    xml = ('<?xml version="1.0"?><usfx>'
           '<book id="GEN"><h>Genesis</h><c id="1"/>'
           '<v id="1"/> In principio creavit Deus cælum et terram.<ve/>'
           '<v id="2"/> Terra autem erat inanis et vacua.<ve/>'
           '</book>'
           '<book id="1PE"><c id="3"/><v id="18"/> Quia et Christus.<ve/></book>'
           '</usfx>')
    out = list(fetch.normalize_usfx(xml))
    books = {osis: verses for osis, verses in out}
    assert "Gen" in books and "1Pet" in books
    gen = {vv.verse: vv.text for vv in books["Gen"]}
    assert gen[1].startswith("In principio creavit Deus")
    assert gen[2].startswith("Terra autem")
    assert books["1Pet"][0].text.startswith("Quia et Christus")


def test_usfx_to_osis_handles_cases():
    from exeg import fetch
    assert fetch._usfx_to_osis("GEN") == "Gen"
    assert fetch._usfx_to_osis("gen") == "Gen"
    assert fetch._usfx_to_osis("1PE") == "1Pet"
    assert fetch._usfx_to_osis("BOGUS") is None


def test_optional_pack_fetches_in_dependency_order_and_skips(monkeypatch):
    calls = []
    monkeypatch.setattr(fetch, "dataset_installed", lambda name: name == "wlc")
    monkeypatch.setattr(fetch, "fetch_strongs", lambda log=print: calls.append("strongs"))
    monkeypatch.setattr(fetch, "fetch_sblgnt", lambda log=print: calls.append("sblgnt"))
    monkeypatch.setattr(fetch, "fetch_wlc", lambda log=print: calls.append("wlc"))
    monkeypatch.setattr(fetch, "fetch_ebible",
                        lambda versions=None, log=print: calls.extend(versions))
    monkeypatch.setattr(fetch, "fetch_vulgate", lambda log=print: calls.append("vulgate"))
    fetch.fetch_optional_pack(log=lambda _msg: None)
    assert calls == ["strongs", "sblgnt", "web", "kjv", "vulgate"]


def test_optional_pack_status(monkeypatch):
    monkeypatch.setattr(fetch, "dataset_installed", lambda _name: False)
    monkeypatch.setattr(fetch, "dataset_present", lambda _name: False)
    assert fetch.optional_pack_status() == "not_installed"
    monkeypatch.setattr(fetch, "dataset_present", lambda name: name == "web")
    assert fetch.optional_pack_status() == "partial"
    monkeypatch.setattr(fetch, "dataset_installed", lambda _name: True)
    assert fetch.optional_pack_status() == "installed"
