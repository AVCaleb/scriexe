"""Plain-TSV corpus storage. data/corpus/{version}/{osis}.tsv is the source of truth."""
import os
from dataclasses import dataclass
from pathlib import Path

WORD_VERSIONS = {"sblgnt", "wlc"}


def root() -> Path:
    env = os.environ.get("EXEG_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def corpus_dir() -> Path:
    return root() / "data" / "corpus"


def cache_dir() -> Path:
    p = root() / "data" / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sources_dir() -> Path:
    p = root() / "data" / "sources"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class Verse:
    chapter: int
    verse: int
    text: str


@dataclass(frozen=True)
class Word:
    chapter: int
    verse: int
    idx: int
    surface: str
    lemma: str
    strongs: str
    morph: str


def _path(version: str, osis: str) -> Path:
    return corpus_dir() / version / f"{osis}.tsv"


def _write_rows(version: str, osis: str, rows) -> None:
    path = _path(version, osis)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")


def write_verses(version: str, osis: str, verses: list[Verse]) -> None:
    _write_rows(version, osis, ((v.chapter, v.verse, v.text) for v in verses))


def write_words(version: str, osis: str, words: list[Word]) -> None:
    _write_rows(version, osis, ((w.chapter, w.verse, w.idx, w.surface, w.lemma, w.strongs, w.morph) for w in words))


def read_verses(version: str, osis: str) -> list[Verse]:
    path = _path(version, osis)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ch, v, text = line.split("\t", 2)
        out.append(Verse(int(ch), int(v), text))
    return out


def read_words(version: str, osis: str) -> list[Word]:
    path = _path(version, osis)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ch, v, idx, surface, lemma, strongs, morph = line.split("\t")
        out.append(Word(int(ch), int(v), int(idx), surface, lemma, strongs, morph))
    return out


def has_version(version: str) -> bool:
    d = corpus_dir() / version
    return d.is_dir() and any(d.glob("*.tsv"))


def has_book(version: str, osis: str) -> bool:
    return _path(version, osis).exists()


def get_words(ref, version: str) -> list[Word]:
    return [w for w in read_words(version, ref.book.osis) if ref.contains(w.chapter, w.verse)]


def get_verses(version: str, ref) -> list[Verse]:
    osis = ref.book.osis
    if version in WORD_VERSIONS:
        verses: dict[tuple[int, int], list[str]] = {}
        for w in get_words(ref, version):
            verses.setdefault((w.chapter, w.verse), []).append(w.surface.replace("/", ""))
        return [Verse(ch, v, " ".join(parts)) for (ch, v), parts in sorted(verses.items())]
    return [v for v in read_verses(version, osis) if ref.contains(v.chapter, v.verse)]
