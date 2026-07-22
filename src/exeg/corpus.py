"""Plain-TSV corpus storage. data/corpus/{version}/{osis}.tsv is the source of truth."""
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

WORD_VERSIONS = {"sblgnt", "wlc"}


def default_user_root(system: str | None = None) -> Path:
    system = system or platform.system()
    home = Path(os.environ.get("HOME", "~")).expanduser()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "scriexe"
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return base / "scriexe"
    base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return base / "scriexe"


def _source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def user_root() -> Path:
    if os.environ.get("EXEG_ROOT"):
        return Path(os.environ["EXEG_ROOT"])
    if os.environ.get("EXEG_USER_ROOT"):
        return Path(os.environ["EXEG_USER_ROOT"])
    if getattr(sys, "frozen", False):
        return default_user_root()
    return _source_root()


def resource_root() -> Path:
    if os.environ.get("EXEG_RESOURCE_ROOT"):
        return Path(os.environ["EXEG_RESOURCE_ROOT"])
    if os.environ.get("EXEG_ROOT"):
        return Path(os.environ["EXEG_ROOT"])
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _source_root()


def root() -> Path:
    """Writable application root (repository root in source-checkout mode)."""
    return user_root()


def corpus_dir() -> Path:
    return user_root() / "data" / "corpus"


def corpus_dirs() -> list[Path]:
    dirs = [corpus_dir(), resource_root() / "data" / "corpus"]
    return list(dict.fromkeys(dirs))


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


def _read_path(version: str, osis: str) -> Path:
    relative = Path(version) / f"{osis}.tsv"
    return next((d / relative for d in corpus_dirs() if (d / relative).exists()),
                corpus_dir() / relative)


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
    path = _read_path(version, osis)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ch, v, text = line.split("\t", 2)
        out.append(Verse(int(ch), int(v), text))
    return out


def read_words(version: str, osis: str) -> list[Word]:
    path = _read_path(version, osis)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ch, v, idx, surface, lemma, strongs, morph = line.split("\t")
        out.append(Word(int(ch), int(v), int(idx), surface, lemma, strongs, morph))
    return out


def has_version(version: str) -> bool:
    return any((d / version).is_dir() and any((d / version).glob("*.tsv"))
               for d in corpus_dirs())


def has_book(version: str, osis: str) -> bool:
    return _read_path(version, osis).exists()


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
