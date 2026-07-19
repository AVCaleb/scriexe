"""API.Bible client used for NASB95. Verse-level fetch and cache (cap 500)."""
import json
import os
import re
import time
import urllib.request

from exeg import corpus
from exeg.refs import Ref

BASE = "https://api.scripture.api.bible/v1"
NOTICE = ("Scripture quotations taken from the NASB® New American Standard Bible®, "
          "Copyright © 1960, 1971, 1977, 1995 by The Lockman Foundation. "
          "Used by permission. All rights reserved. lockman.org")
CAP = 500


class Unavailable(Exception):
    pass


def _http_json(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"api-key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _cache_path():
    return corpus.cache_dir() / "nasb95.json"


def _load_cache() -> dict:
    p = _cache_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"verses": {}, "chapter_verses": {}, "bible_id": None}


def _save_cache(cache: dict) -> None:
    vs = cache["verses"]
    if len(vs) > CAP:
        for k in sorted(vs, key=lambda k: vs[k]["at"])[: len(vs) - CAP]:
            del vs[k]
    _cache_path().write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _key_env() -> str:
    key = os.environ.get("API_BIBLE_KEY")
    if not key:
        raise Unavailable("NASB95 unavailable — set API_BIBLE_KEY in .env "
                          "(free key: scripture.api.bible) or run `exeg import`")
    return key


def _bible_id(cache: dict, key: str) -> str:
    if cache.get("bible_id"):
        return cache["bible_id"]
    try:
        data = _http_json(f"{BASE}/bibles?language=eng", key).get("data", [])
    except Exception as e:
        raise Unavailable(f"API.Bible error: {e}") from e
    nasb = [b for b in data
            if "NASB" in (b.get("abbreviation", "") + b.get("abbreviationLocal", ""))]
    nasb.sort(key=lambda b: "1995" not in b.get("name", ""))
    if not nasb:
        raise Unavailable("NASB95 is not available on this API.Bible key — "
                          "use `exeg import` with your own licensed copy instead")
    cache["bible_id"] = nasb[0]["id"]
    return cache["bible_id"]


def _chapter_verse_ids(cache: dict, key: str, bid: str, usfm: str, ch: int) -> list[str]:
    ck = f"{usfm}.{ch}"
    if ck not in cache["chapter_verses"]:
        try:
            data = _http_json(f"{BASE}/bibles/{bid}/chapters/{ck}/verses", key).get("data", [])
        except Exception as e:
            raise Unavailable(f"API.Bible error: {e}") from e
        cache["chapter_verses"][ck] = [d["id"] for d in data]
    return cache["chapter_verses"][ck]


def _fetch_verse(key: str, bid: str, vid: str) -> str:
    url = (f"{BASE}/bibles/{bid}/verses/{vid}?content-type=text"
           "&include-notes=false&include-titles=false&include-verse-numbers=false")
    try:
        content = _http_json(url, key).get("data", {}).get("content", "")
    except Exception as e:
        raise Unavailable(f"API.Bible error: {e}") from e
    return re.sub(r"^\s*\[?\d+\]?\s*", "", re.sub(r"\s+", " ", content)).strip()


def get_passage(ref: Ref) -> dict:
    cache = _load_cache()
    usfm = ref.book.usfm
    key = None

    def ensure_key():
        nonlocal key
        if key is None:
            key = _key_env()
        return key

    wanted: list[tuple[int, int]] = []
    for ch in range(ref.chapter, ref.end_chapter + 1):
        cached_ids = cache["chapter_verses"].get(f"{usfm}.{ch}")
        if cached_ids is None:
            bid = _bible_id(cache, ensure_key())
            cached_ids = _chapter_verse_ids(cache, ensure_key(), bid, usfm, ch)
        for vid in cached_ids:
            v = int(vid.rsplit(".", 1)[1])
            if ref.contains(ch, v):
                wanted.append((ch, v))

    out: dict[tuple[int, int], str] = {}
    now = time.time()
    dirty = False
    for ch, v in wanted:
        k = f"{usfm}.{ch}.{v}"
        entry = cache["verses"].get(k)
        if entry is None:
            bid = _bible_id(cache, ensure_key())
            text = _fetch_verse(ensure_key(), bid, k)
            cache["verses"][k] = {"t": text, "at": now}
            dirty = True
        out[(ch, v)] = cache["verses"][k]["t"]
    if dirty or cache.get("bible_id"):
        _save_cache(cache)
    if not out:
        raise Unavailable(f"NASB95: no verses found for {ref.en_label()}")
    return out
