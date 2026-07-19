"""Corpus search and word study (exeg search / exeg word)."""
import json
import re
import sys
import unicodedata

from exeg import canon, corpus

_TENSE = {"P": "present", "I": "imperfect", "F": "future", "A": "aorist", "X": "perfect", "Y": "pluperfect"}
_VOICE = {"A": "active", "M": "middle", "P": "passive"}
_MOOD = {"I": "indicative", "D": "imperative", "S": "subjunctive", "O": "optative",
         "N": "infinitive", "P": "participle"}
_CASE = {"N": "nom", "G": "gen", "D": "dat", "A": "acc", "V": "voc"}
_NUM = {"S": "sg", "P": "pl"}
_GEND = {"M": "m", "F": "f", "N": "n"}


def greek_morph_label(morph: str) -> str:
    if "/" not in morph:
        return morph
    pos, _, p = morph.partition("/")
    if len(p) != 8:
        return morph
    person, tense, voice, mood, case, num, gend = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
    if pos.startswith("V"):
        parts = [_TENSE.get(tense, ""), _VOICE.get(voice, ""), _MOOD.get(mood, "")]
        if mood == "P":
            parts.append(f"{_CASE.get(case, '')} {_NUM.get(num, '')} {_GEND.get(gend, '')}".strip())
        elif person in "123":
            parts.append(f"{person}{_NUM.get(num, '')}")
        label = " ".join(x for x in parts if x)
    else:
        label = " ".join(x for x in (_CASE.get(case, ""), _NUM.get(num, ""), _GEND.get(gend, "")) if x)
    return label or morph


def _strongs_dicts() -> tuple[dict, dict, dict]:
    sdir = corpus.corpus_dir() / "strongs"

    def load(name):
        p = sdir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    return load("greek.json"), load("hebrew.json"), load("greek-lemma-map.json")


def search_text(pattern, versions, book=None, lemma=False):
    rx = re.compile(pattern, re.IGNORECASE)
    hits = []
    for version in versions:
        books = [book] if book else [b.osis for b in canon.BOOKS]
        for osis in books:
            if lemma and version in corpus.WORD_VERSIONS:
                seen = set()
                for w in corpus.read_words(version, osis):
                    if rx.search(w.lemma) and (w.chapter, w.verse) not in seen:
                        seen.add((w.chapter, w.verse))
                        hits.append((version, osis, w.chapter, w.verse, w.surface))
            else:
                for v in corpus.read_verses(version, osis):
                    if rx.search(v.text):
                        hits.append((version, osis, v.chapter, v.verse, v.text))
    return hits


def word_occurrences(query: str) -> dict:
    greek, hebrew, lemma_map = _strongs_dicts()
    q = query.strip()
    strongs = lemma = ""
    if re.fullmatch(r"[GHgh]\d+", q):
        strongs = q.upper()
    else:
        lemma = unicodedata.normalize("NFC", q)
        strongs = lemma_map.get(lemma, "")
        if not strongs:
            for code, e in hebrew.items():
                if unicodedata.normalize("NFC", e.get("lemma", "") or "") == lemma:
                    strongs = code
                    break
    occurrences = []
    for version in sorted(corpus.WORD_VERSIONS):
        for b in canon.BOOKS:
            for w in corpus.read_words(version, b.osis):
                if (strongs and w.strongs == strongs) or (lemma and unicodedata.normalize("NFC", w.lemma) == lemma):
                    occurrences.append((version, b.osis, w.chapter, w.verse, w.surface, w.morph))
                    if not lemma and w.lemma:
                        lemma = unicodedata.normalize("NFC", w.lemma)
    entry = greek.get(strongs) or hebrew.get(strongs) or {}
    by_book: dict[str, int] = {}
    for _, osis, *_rest in occurrences:
        by_book[osis] = by_book.get(osis, 0) + 1
    return {"query": query, "strongs": strongs, "lemma": lemma or entry.get("lemma", ""),
            "gloss": entry.get("strongs_def", "") or entry.get("kjv_def", ""),
            "occurrences": occurrences, "by_book": by_book}


def cmd_search(args) -> int:
    versions = args.versions.split(",") if args.versions else (["web", "kjv", "cuvs"] if not args.lemma else ["sblgnt", "wlc"])
    book = canon.find_book(args.book).osis if args.book else None
    hits = search_text(args.pattern, versions, book=book, lemma=args.lemma)
    for version, osis, ch, v, text in hits[: args.limit]:
        print(f"{version:7s} {osis} {ch}:{v}  {text}")
    extra = len(hits) - args.limit
    if extra > 0:
        print(f"... and {extra} more (raise --limit)")
    if not hits:
        print("no matches", file=sys.stderr)
        return 1
    return 0


def cmd_word(args) -> int:
    r = word_occurrences(args.query)
    if not r["occurrences"]:
        print(f"no occurrences of {args.query!r} in the corpus", file=sys.stderr)
        return 1
    head = f"{r['lemma']} — {r['strongs'] or 'no Strong’s match'}"
    if r["gloss"]:
        head += f" · {r['gloss']}"
    print(head)
    for osis, n in r["by_book"].items():
        print(f"  {osis}: {n}×")
    for version, osis, ch, v, surface, morph in r["occurrences"][: args.limit]:
        print(f"  {osis} {ch}:{v}  {surface}  ({greek_morph_label(morph)})")
    return 0
