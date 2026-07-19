import json
import pytest
from exeg import corpus, esv
from exeg.refs import parse_ref

PASSAGE = {"passages": ["[18] For Christ also suffered once for sins, [19] in which he went and proclaimed"]}
CROSS = {"passages": ["[31] And God saw everything. [1] Thus the heavens [2] and on the seventh day"]}

def test_no_key_raises_unavailable(corpus_root, monkeypatch):
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    with pytest.raises(esv.Unavailable, match="ESV_API_KEY"):
        esv.get_passage(parse_ref("1Pet 3:18-19"))

def test_fetch_parses_markers_and_caches(corpus_root, monkeypatch):
    monkeypatch.setenv("ESV_API_KEY", "k")
    calls = []
    monkeypatch.setattr(esv, "_http_json", lambda url, headers: calls.append(url) or PASSAGE)
    got = esv.get_passage(parse_ref("1Pet 3:18-19"))
    assert got[(3, 18)].startswith("For Christ also suffered")
    assert got[(3, 19)].startswith("in which he went")
    assert len(calls) == 1
    # second call served from cache — no HTTP
    esv.get_passage(parse_ref("1Pet 3:18-19"))
    assert len(calls) == 1

def test_chapter_rollover(corpus_root, monkeypatch):
    monkeypatch.setenv("ESV_API_KEY", "k")
    monkeypatch.setattr(esv, "_http_json", lambda url, headers: CROSS)
    got = esv.get_passage(parse_ref("Gen 1:31-2:2"))
    assert (1, 31) in got and (2, 1) in got and (2, 2) in got

def test_http_failure_with_cold_cache_raises(corpus_root, monkeypatch):
    monkeypatch.setenv("ESV_API_KEY", "k")
    def boom(url, headers):
        raise OSError("network down")
    monkeypatch.setattr(esv, "_http_json", boom)
    with pytest.raises(esv.Unavailable, match="network down"):
        esv.get_passage(parse_ref("1Pet 3:18"))

def test_cache_capped_at_500(corpus_root, monkeypatch):
    monkeypatch.setenv("ESV_API_KEY", "k")
    path = corpus.cache_dir() / "esv.json"
    verses = {f"Ps.{c}.{v}": {"t": "x", "at": float(c * 200 + v)} for c in (1, 2, 3) for v in range(1, 200)}
    path.write_text(json.dumps({"verses": verses, "chapters": []}))
    monkeypatch.setattr(esv, "_http_json", lambda url, headers: PASSAGE)
    esv.get_passage(parse_ref("1Pet 3:18-19"))
    saved = json.loads(path.read_text())
    assert len(saved["verses"]) <= 500
    assert "1Pet.3.18" in saved["verses"]          # newest kept

def test_eviction_invalidates_chapter_marker(corpus_root, monkeypatch):
    monkeypatch.setenv("ESV_API_KEY", "k")
    path = corpus.cache_dir() / "esv.json"
    verses = {f"Ps.1.{v}": {"t": "x", "at": 1.0} for v in range(1, 7)}
    verses.update({f"Isa.{c}.{v}": {"t": "y", "at": 1000.0 + c * 200 + v}
                   for c in (1, 2, 3) for v in range(1, 180)})
    path.write_text(json.dumps({"verses": verses, "chapters": ["Ps.1"]}))
    monkeypatch.setattr(esv, "_http_json", lambda url, headers: PASSAGE)
    esv.get_passage(parse_ref("1Pet 3:18-19"))          # triggers save + eviction
    saved = json.loads(path.read_text())
    assert "Ps.1" not in saved["chapters"]              # marker invalidated with its verses
    calls = []
    monkeypatch.setattr(esv, "_http_json", lambda url, headers: calls.append(url) or {"passages": ["[1] a [2] b [3] c [4] d [5] e [6] f"]})
    esv.get_passage(parse_ref("Ps 1"))                  # must re-fetch, not serve stale partial
    assert calls

def test_cross_chapter_served_from_fully_cached_chapters(corpus_root, monkeypatch):
    monkeypatch.setenv("ESV_API_KEY", "k")
    path = corpus.cache_dir() / "esv.json"
    verses = {f"Gen.1.{v}": {"t": f"g1v{v}", "at": 1.0} for v in (30, 31)}
    verses.update({f"Gen.2.{v}": {"t": f"g2v{v}", "at": 1.0} for v in (1, 2, 3)})
    path.write_text(json.dumps({"verses": verses, "chapters": ["Gen.1", "Gen.2"]}))
    def boom(url, headers):
        raise AssertionError("cache should have satisfied this")
    monkeypatch.setattr(esv, "_http_json", boom)
    got = esv.get_passage(parse_ref("Gen 1:31-2:2"))
    assert got == {(1, 31): "g1v31", (2, 1): "g2v1", (2, 2): "g2v2"}
