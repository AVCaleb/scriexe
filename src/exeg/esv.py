"""Crossway ESV API client. Passage-level fetch, verse-level cache capped at 500 entries."""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from exeg import corpus
from exeg.refs import Ref

API = "https://api.esv.org/v3/passage/text/"
PARAMS = ("include-passage-references=false&include-verse-numbers=true"
          "&include-first-verse-numbers=true&include-footnotes=false"
          "&include-headings=false&include-short-copyright=false")
NOTICE = ("Scripture quotations marked “ESV” are from the ESV® Bible "
          "(The Holy Bible, English Standard Version®), © 2001 by Crossway. "
          "Used by permission. All rights reserved.")
CAP = 500
_MARKER = re.compile(r"\[(\d+)\]\s*([^\[]*)")


class Unavailable(Exception):
    pass


def _http_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _cache_path():
    return corpus.cache_dir() / "esv.json"


def _load_cache() -> dict:
    p = _cache_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"verses": {}, "chapters": []}


def _save_cache(cache: dict) -> None:
    vs = cache["verses"]
    if len(vs) > CAP:
        evict = sorted(vs, key=lambda k: vs[k]["at"])[: len(vs) - CAP]
        gone = {k.rsplit(".", 1)[0] for k in evict}
        for k in evict:
            del vs[k]
        cache["chapters"] = [c for c in cache["chapters"] if c not in gone]
    _cache_path().write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _key(osis: str, ch: int, v: int) -> str:
    return f"{osis}.{ch}.{v}"


def _from_cache(cache: dict, ref: Ref):
    osis = ref.book.osis
    if ref.verse is None:
        if f"{osis}.{ref.chapter}" not in cache["chapters"]:
            return None
        out = {}
        for k, e in cache["verses"].items():
            b, ch, v = k.rsplit(".", 2)
            if b == osis and int(ch) == ref.chapter:
                out[(int(ch), int(v))] = e["t"]
        return out or None
    if ref.chapter == ref.end_chapter:
        need = [(ref.chapter, v) for v in range(ref.verse, ref.end_verse + 1)]
        if all(_key(osis, ch, v) in cache["verses"] for ch, v in need):
            return {(ch, v): cache["verses"][_key(osis, ch, v)]["t"] for ch, v in need}
        return None
    # cross-chapter: serve from cache only when every covered chapter is fully cached
    if all(f"{osis}.{ch}" in cache["chapters"] for ch in range(ref.chapter, ref.end_chapter + 1)):
        out = {}
        for k, e in cache["verses"].items():
            b, ch, v = k.rsplit(".", 2)
            if b == osis and ref.contains(int(ch), int(v)):
                out[(int(ch), int(v))] = e["t"]
        return out or None
    return None


def _parse_passage(text: str, start_chapter: int) -> dict:
    out, ch, prev = {}, start_chapter, 0
    for num, body in _MARKER.findall(text):
        n = int(num)
        if n <= prev:
            ch += 1
        prev = n
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            out[(ch, n)] = body
    return out


def get_passage(ref: Ref) -> dict:
    cache = _load_cache()
    cached = _from_cache(cache, ref)
    if cached:
        return cached
    key = os.environ.get("ESV_API_KEY")
    if not key:
        raise Unavailable("ESV unavailable — set ESV_API_KEY in .env (free key: api.esv.org)")
    q = urllib.parse.quote(ref.en_label().replace("–", "-"))
    try:
        data = _http_json(f"{API}?q={q}&{PARAMS}", {"Authorization": f"Token {key}"})
        passages = data.get("passages") or []
        if not passages:
            raise Unavailable(f"ESV returned no text for {ref.en_label()}")
        got = _parse_passage(passages[0], ref.chapter)
    except Unavailable:
        raise
    except Exception as e:
        raise Unavailable(f"ESV API error: {e}") from e
    now = time.time()
    for (ch, v), t in got.items():
        cache["verses"][_key(ref.book.osis, ch, v)] = {"t": t, "at": now}
    if ref.verse is None and f"{ref.book.osis}.{ref.chapter}" not in cache["chapters"]:
        cache["chapters"].append(f"{ref.book.osis}.{ref.chapter}")
    _save_cache(cache)
    return got
