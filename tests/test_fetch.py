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


# ---- CUVS upstream text fixes (GitHub issue #1) ---------------------------

def _cuvs(osis, chapter, verse, text):
    from exeg.corpus import Verse
    return fetch._apply_cuvs_fixes(osis, [Verse(chapter, verse, text)])[0].text


def test_cuvs_fix_replaces_corrupted_glyph():
    # ⶍ (U+2D8D ETHIOPIC SYLLABLE DDOA) is a corrupted 墩 in eBible cmn-cu89s
    assert "树墩子" in _cuvs("Isa", 6, 13, "像栗树、橡树虽被砍伐， 树ⶍ子却仍存留。")
    assert "木墩子" in _cuvs("Isa", 44, 19, "我岂可向木ⶍ子叩拜呢？」")


def test_cuvs_fix_restores_missing_lun():
    assert "耶书仑" in _cuvs("Isa", 44, 2, "我所拣选的 耶书 哪， 不要害怕！")
    assert "沙仑" in _cuvs("Isa", 35, 2, "并 迦密与 沙 的华美，必赐给它。")
    assert "拉沙仑" in _cuvs("Josh", 12, 18, "一个是 亚弗王，一个是 拉沙 王，")


def test_cuvs_fix_restores_missing_chen():
    assert "茵陈" in _cuvs("Jer", 9, 15, "我必将茵 给这百姓吃")
    assert "茵陈" in _cuvs("Jer", 23, 15, "我必将茵 给他们吃")
    # Rev 8:11 has two occurrences in one verse — both must be fixed
    text = _cuvs("Rev", 8, 11, "（这星名叫「茵 」。）众水的三分之一变为茵 ，因水变苦")
    assert text.count("茵陈") == 2


def test_cuvs_fix_leaves_unrelated_verses_alone():
    # 以利沙 (Elisha) ends with 沙 but is not missing 仑
    text = "以利沙 对仆人说：「究竟当为她做什么呢？」"
    assert _cuvs("2Kgs", 4, 14, text) == text
    # no fix registered for this verse at all
    text = "起初 神创造天地。"
    assert _cuvs("Gen", 1, 1, text) == text


# ---- download() resilience --------------------------------------------------

def _http_error(code, headers=None):
    import io
    import urllib.error
    return urllib.error.HTTPError("https://x.test/f", code, "err",
                                  headers or {}, io.BytesIO(b""))


def test_download_retries_on_429_then_succeeds(tmp_path, monkeypatch):
    import urllib.request
    calls = []
    sleeps = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"payload"

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise _http_error(429)
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "f.txt"
    result = fetch.download("https://x.test/f", dest, sleep=sleeps.append)
    assert result.read_bytes() == b"payload"
    assert len(calls) == 3
    assert sleeps == [2, 4]  # exponential backoff between attempts


def test_download_honors_retry_after_header(tmp_path, monkeypatch):
    import email.message
    import urllib.request
    sleeps = []
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"ok"

    headers = email.message.Message()
    headers["Retry-After"] = "7"

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(429, headers)
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    fetch.download("https://x.test/f", tmp_path / "f.txt", sleep=sleeps.append)
    assert sleeps == [7]


def test_download_gives_up_after_max_retries(tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(429)))
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        fetch.download("https://x.test/f", tmp_path / "f.txt",
                       sleep=lambda _s: None)


def test_download_does_not_retry_other_errors(tmp_path, monkeypatch):
    import urllib.request
    calls = []

    def fake_urlopen(*a, **k):
        calls.append(1)
        raise _http_error(404)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        fetch.download("https://x.test/f", tmp_path / "f.txt",
                       sleep=lambda _s: None)
    assert len(calls) == 1


def test_download_retries_on_5xx(tmp_path, monkeypatch):
    import urllib.request
    calls = []
    sleeps = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"payload"

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(503)
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "f.txt"
    fetch.download("https://x.test/f", dest, sleep=sleeps.append)
    assert dest.read_bytes() == b"payload"
    assert len(calls) == 2 and sleeps == [2]
