import pytest
from exeg import apibible
from exeg.refs import parse_ref

BIBLES = {"data": [
    {"id": "kjv-id", "abbreviation": "KJV", "name": "King James Version"},
    {"id": "nasb-id", "abbreviation": "NASB", "name": "New American Standard Bible 1995"},
]}
CHAPTER = {"data": [{"id": "1PE.3.18"}, {"id": "1PE.3.19"}]}

def fake_http(url, key):
    if url.endswith("/bibles?language=eng"):
        return BIBLES
    if "/chapters/1PE.3/verses" in url:
        return CHAPTER
    if "/verses/1PE.3.18" in url:
        return {"data": {"content": "  18 For Christ also died for sins once for all  "}}
    if "/verses/1PE.3.19" in url:
        return {"data": {"content": "19 in which also He went"}}
    raise AssertionError(f"unexpected url {url}")

def test_no_key_raises(corpus_root, monkeypatch):
    monkeypatch.delenv("API_BIBLE_KEY", raising=False)
    with pytest.raises(apibible.Unavailable, match="API_BIBLE_KEY"):
        apibible.get_passage(parse_ref("1Pet 3:18"))

def test_fetch_range_and_cache(corpus_root, monkeypatch):
    monkeypatch.setenv("API_BIBLE_KEY", "k")
    calls = []
    monkeypatch.setattr(apibible, "_http_json", lambda url, key: calls.append(url) or fake_http(url, key))
    got = apibible.get_passage(parse_ref("1Pet 3:18-19"))
    assert got[(3, 18)] == "For Christ also died for sins once for all"
    assert got[(3, 19)] == "in which also He went"
    n = len(calls)
    apibible.get_passage(parse_ref("1Pet 3:18-19"))
    assert len(calls) == n            # fully served from cache

def test_no_nasb_on_key_raises(corpus_root, monkeypatch):
    monkeypatch.setenv("API_BIBLE_KEY", "k")
    monkeypatch.setattr(apibible, "_http_json",
                        lambda url, key: {"data": [{"id": "x", "abbreviation": "KJV", "name": "KJV"}]})
    with pytest.raises(apibible.Unavailable, match="exeg import"):
        apibible.get_passage(parse_ref("1Pet 3:18"))
