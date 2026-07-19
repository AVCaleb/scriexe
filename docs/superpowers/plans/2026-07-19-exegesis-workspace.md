# Exegesis Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `exeg`, a stdlib-only Python CLI that maintains a local multilingual Bible corpus (SBLGNT, WLC, WEB, KJV, 和合本, Strong's) plus licensed ESV/NASB95 passage fetching, and scaffolds bilingual (EN/中文) exegesis study files.

**Architecture:** A plain-TSV corpus under `data/corpus/` (one file per book per version; word-per-row for Greek/Hebrew with lemma/Strong's/morphology) is the source of truth. A thin module stack — canon → refs → corpus → usfm/fetch → display/esv/apibible/importer/search/scaffold — is dispatched by one argparse CLI. Copyrighted ESV/NASB95 text is fetched per passage through official APIs and cached under `data/cache/` within license caps.

**Tech Stack:** Python ≥ 3.10, stdlib only at runtime (urllib, zipfile, xml.etree, json, re, argparse, difflib, unicodedata). pytest (dev-only). setuptools build backend.

**Spec:** `docs/superpowers/specs/2026-07-19-exegesis-workspace-design.md`

**Deviation from spec (flagged for the user, approved rationale):** the spec lists `data/corpus.sqlite` as a derived index. The whole corpus is < 20 MB of TSV; linear scans answer every query in well under a second, so the index is YAGNI and is **not built**. If `word`/`search` ever feel slow, add an index then.

## Global Constraints

- Python ≥ 3.10; **zero runtime dependencies** (stdlib only). `pytest>=8` as the only dev dependency.
- **No network access in tests.** All HTTP goes through module-level `_http_*` functions that tests monkeypatch; normalizers take strings/paths.
- All of `data/` is gitignored (rebuildable or licensed-user-only content). `studies/` is tracked (it's the user's work), kept via `studies/.gitkeep`.
- Project root resolution: `EXEG_ROOT` env var if set, else two levels above `src/exeg/` — tests always set `EXEG_ROOT` to a tmp dir.
- ESV and NASB95 caches are each capped at **500 verse entries** (license-conservative), oldest-first eviction.
- Bilingual heading strings must match the spec exactly, e.g. `## Text · 经文对照`, `## Word Studies · 字词研究`, `## Structure & Context · 结构与背景`, `## Interpretation · 释经结论`, `## Theology & Application · 神学综合与应用`.
- API keys come from environment or a gitignored `.env` in the project root: `ESV_API_KEY`, `API_BIBLE_KEY`.
- Run all commands from `/Users/caleb/Projects/exegesis`; use `.venv/bin/pytest` and `.venv/bin/exeg` (no activation assumed).
- Commit after every task with the message given in the task.

## File Structure

```
pyproject.toml           # packaging + pytest config
.gitignore
AGENTS.md                # cross-agent contract   (Task 13)
CLAUDE.md                # pointer to AGENTS.md   (Task 13)
README.md                # Task 13
studies/.gitkeep
src/exeg/
  __init__.py            # __version__
  cli.py                 # argparse dispatch only — no logic
  canon.py               # 66-book table, lookup, aliases, chapter counts
  refs.py                # reference parsing (EN + 中文) → Ref
  corpus.py              # TSV read/write, Verse/Word records, root()
  usfm.py                # minimal USFM → verses
  fetch.py               # download + normalize + integrity  (exeg fetch)
  display.py             # parallel passage rendering         (exeg passage)
  esv.py                 # Crossway ESV API client + capped cache
  apibible.py            # API.Bible NASB95 client + capped cache
  importer.py            # user-licensed file import          (exeg import)
  search.py              # text/lemma search + word study     (exeg search/word)
  scaffold.py            # study-file generation              (exeg scaffold)
tests/
  conftest.py            # corpus_root fixture (EXEG_ROOT → tmp)
  test_canon.py test_refs.py test_corpus.py test_usfm.py test_fetch.py
  test_display.py test_esv.py test_apibible.py test_importer.py
  test_search.py test_scaffold.py
```

**Verified data sources (all checked live 2026-07-19):**

| Source | URL pattern |
|---|---|
| MorphGNT | `https://raw.githubusercontent.com/morphgnt/sblgnt/master/{NN-Code}-morphgnt.txt`, files `61-Mt` … `87-Re` (list in Task 6) |
| OSHB/WLC | `https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/{Osis}.xml` (OSIS ids, `Gen.xml` … `Mal.xml`) |
| ebible.org | `https://ebible.org/Scriptures/{id}_usfm.zip` for `engwebp` (WEB), `eng-kjv` (KJV), `cmn-cu89s` (和合本简体) |
| Strong's | `https://raw.githubusercontent.com/openscriptures/strongs/master/greek/strongs-greek-dictionary.js` and `.../hebrew/strongs-hebrew-dictionary.js` |

**Verified formats:** MorphGNT line = `BBCCVV pos parsing text word normalized lemma` (space-separated, `BB` = NT book 01–27). OSHB = OSIS XML, `<verse osisID="Gen.1.1">` containing `<w lemma="b/7225" morph="HR/Ncfsa">בְּ/רֵאשִׁ֖ית</w>` — digits in `lemma` are Strong's numbers; `/` marks segment boundaries. Strong's `.js` = header comment + `var x = {...};` where `{...}` is JSON keyed `"G1"`/`"H1"` with fields `lemma`, `translit`/`xlit`, `strongs_def`, `kjv_def`.

---

### Task 1: Project skeleton and CLI entry point

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `studies/.gitkeep`, `src/exeg/__init__.py`, `src/exeg/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `exeg.cli.main(argv: list[str] | None = None) -> int`, console script `exeg`. Subcommands are registered in `cli.py` by later tasks; each later task adds one `sub.add_parser(...)` block and a `cmd_*` handler import.

- [ ] **Step 1: Write config files**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "exeg"
version = "0.1.0"
description = "Terminal Bible exegesis workspace"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
exeg = "exeg.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.gitignore`:

```
.venv/
data/
__pycache__/
*.egg-info/
.env
.DS_Store
```

Create `studies/.gitkeep` as an empty file.

- [ ] **Step 2: Write the failing test**

`tests/test_cli.py`:

```python
from exeg.cli import main

def test_no_args_prints_help_and_fails(capsys):
    assert main([]) == 2
    assert "exeg" in capsys.readouterr().err

def test_version_flag(capsys):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out
```

- [ ] **Step 3: Create venv, install, run test to verify it fails**

```bash
python3 -m venv .venv
.venv/bin/pip install -q -e '.[dev]'
.venv/bin/pytest tests/test_cli.py -q
```

Expected: FAIL (`ModuleNotFoundError: No module named 'exeg'` or import error — `cli.py` doesn't exist yet).

- [ ] **Step 4: Implement**

`src/exeg/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/exeg/cli.py`:

```python
"""exeg — terminal Bible exegesis workspace. Dispatch only; logic lives in modules."""
import argparse
import os
import sys

from exeg import __version__


def _load_env() -> None:
    """Load KEY=VALUE lines from <root>/.env into os.environ (no override)."""
    from exeg import corpus  # imported lazily; corpus.py arrives in Task 4
    path = corpus.root() / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exeg", description=__doc__)
    p.add_argument("--version", action="store_true", help="print version and exit")
    p.add_subparsers(dest="command")
    return p


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if not args.command:
        parser.print_usage(sys.stderr)
        return 2
    try:
        _load_env()
        return args.func(args)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
```

Note: `_load_env` imports `exeg.corpus`, created in Task 4. Until then no subcommand exists, so the branch never runs and both tests pass.

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_cli.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore studies/.gitkeep src tests
git commit -m "feat: project skeleton with exeg CLI entry point"
```

---

### Task 2: Canon — 66-book table and lookup

**Files:**
- Create: `src/exeg/canon.py`, `tests/test_canon.py`

**Interfaces:**
- Produces:
  - `Book` frozen dataclass: `osis: str, usfm: str, en: str, chapters: int, zh_abbr: str, zh: str, nt: bool`
  - `BOOKS: list[Book]` (canonical order), `BY_OSIS: dict[str, Book]`, `NT_BOOKS: list[Book]`, `USFM_TO_OSIS: dict[str, str]`
  - `WLC_CHAPTERS: dict[str, int]` — MT chapter-count overrides `{"Joel": 4, "Mal": 3}`
  - `max_chapters(book: Book) -> int` — max of English and MT counts
  - `find_book(name: str) -> Book` — raises `UnknownBook(query, suggestions: list[str])` (a `ValueError`)

- [ ] **Step 1: Write the failing test**

`tests/test_canon.py`:

```python
import pytest
from exeg.canon import BOOKS, BY_OSIS, NT_BOOKS, USFM_TO_OSIS, UnknownBook, find_book, max_chapters

def test_table_shape():
    assert len(BOOKS) == 66
    assert len(NT_BOOKS) == 27
    assert NT_BOOKS[0].osis == "Matt" and NT_BOOKS[-1].osis == "Rev"
    assert BY_OSIS["1Pet"].zh == "彼得前书" and BY_OSIS["1Pet"].chapters == 5
    assert USFM_TO_OSIS["1PE"] == "1Pet"

def test_find_book_english_forms():
    for q in ("1Pet", "1 Peter", "1peter", "1PE", "1pe", "gen", "Genesis", "song", "Ps", "mt", "jn"):
        find_book(q)
    assert find_book("1 Peter").osis == "1Pet"
    assert find_book("mt").osis == "Matt"
    assert find_book("ex").osis == "Exod"

def test_find_book_chinese_forms():
    assert find_book("彼前").osis == "1Pet"
    assert find_book("彼得前书").osis == "1Pet"
    assert find_book("创").osis == "Gen"
    assert find_book("启").osis == "Rev"

def test_ambiguous_prefix_raises_with_suggestions():
    with pytest.raises(UnknownBook) as e:
        find_book("ju")          # Judges vs Jude
    assert {"Judg", "Jude"} <= set(e.value.suggestions)

def test_unknown_book_suggests_close_match():
    with pytest.raises(UnknownBook) as e:
        find_book("Filippians")
    assert "Phil" in e.value.suggestions

def test_mt_chapter_overrides():
    assert max_chapters(BY_OSIS["Joel"]) == 4
    assert max_chapters(BY_OSIS["Mal"]) == 4   # max(en 4, MT 3)
    assert max_chapters(BY_OSIS["Gen"]) == 50
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_canon.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.canon`.

- [ ] **Step 3: Implement**

`src/exeg/canon.py` (the table is data — copy it exactly):

```python
"""Canonical book table: OSIS/USFM ids, English and Chinese names, chapter counts."""
import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    osis: str
    usfm: str
    en: str
    chapters: int
    zh_abbr: str
    zh: str
    nt: bool


def _b(osis, usfm, en, ch, zh_abbr, zh, nt=False):
    return Book(osis, usfm, en, ch, zh_abbr, zh, nt)


BOOKS = [
    _b("Gen", "GEN", "Genesis", 50, "创", "创世记"),
    _b("Exod", "EXO", "Exodus", 40, "出", "出埃及记"),
    _b("Lev", "LEV", "Leviticus", 27, "利", "利未记"),
    _b("Num", "NUM", "Numbers", 36, "民", "民数记"),
    _b("Deut", "DEU", "Deuteronomy", 34, "申", "申命记"),
    _b("Josh", "JOS", "Joshua", 24, "书", "约书亚记"),
    _b("Judg", "JDG", "Judges", 21, "士", "士师记"),
    _b("Ruth", "RUT", "Ruth", 4, "得", "路得记"),
    _b("1Sam", "1SA", "1 Samuel", 31, "撒上", "撒母耳记上"),
    _b("2Sam", "2SA", "2 Samuel", 24, "撒下", "撒母耳记下"),
    _b("1Kgs", "1KI", "1 Kings", 22, "王上", "列王纪上"),
    _b("2Kgs", "2KI", "2 Kings", 25, "王下", "列王纪下"),
    _b("1Chr", "1CH", "1 Chronicles", 29, "代上", "历代志上"),
    _b("2Chr", "2CH", "2 Chronicles", 36, "代下", "历代志下"),
    _b("Ezra", "EZR", "Ezra", 10, "拉", "以斯拉记"),
    _b("Neh", "NEH", "Nehemiah", 13, "尼", "尼希米记"),
    _b("Esth", "EST", "Esther", 10, "斯", "以斯帖记"),
    _b("Job", "JOB", "Job", 42, "伯", "约伯记"),
    _b("Ps", "PSA", "Psalms", 150, "诗", "诗篇"),
    _b("Prov", "PRO", "Proverbs", 31, "箴", "箴言"),
    _b("Eccl", "ECC", "Ecclesiastes", 12, "传", "传道书"),
    _b("Song", "SNG", "Song of Solomon", 8, "歌", "雅歌"),
    _b("Isa", "ISA", "Isaiah", 66, "赛", "以赛亚书"),
    _b("Jer", "JER", "Jeremiah", 52, "耶", "耶利米书"),
    _b("Lam", "LAM", "Lamentations", 5, "哀", "耶利米哀歌"),
    _b("Ezek", "EZK", "Ezekiel", 48, "结", "以西结书"),
    _b("Dan", "DAN", "Daniel", 12, "但", "但以理书"),
    _b("Hos", "HOS", "Hosea", 14, "何", "何西阿书"),
    _b("Joel", "JOL", "Joel", 3, "珥", "约珥书"),
    _b("Amos", "AMO", "Amos", 9, "摩", "阿摩司书"),
    _b("Obad", "OBA", "Obadiah", 1, "俄", "俄巴底亚书"),
    _b("Jonah", "JON", "Jonah", 4, "拿", "约拿书"),
    _b("Mic", "MIC", "Micah", 7, "弥", "弥迦书"),
    _b("Nah", "NAM", "Nahum", 3, "鸿", "那鸿书"),
    _b("Hab", "HAB", "Habakkuk", 3, "哈", "哈巴谷书"),
    _b("Zeph", "ZEP", "Zephaniah", 3, "番", "西番雅书"),
    _b("Hag", "HAG", "Haggai", 2, "该", "哈该书"),
    _b("Zech", "ZEC", "Zechariah", 14, "亚", "撒迦利亚书"),
    _b("Mal", "MAL", "Malachi", 4, "玛", "玛拉基书"),
    _b("Matt", "MAT", "Matthew", 28, "太", "马太福音", True),
    _b("Mark", "MRK", "Mark", 16, "可", "马可福音", True),
    _b("Luke", "LUK", "Luke", 24, "路", "路加福音", True),
    _b("John", "JHN", "John", 21, "约", "约翰福音", True),
    _b("Acts", "ACT", "Acts", 28, "徒", "使徒行传", True),
    _b("Rom", "ROM", "Romans", 16, "罗", "罗马书", True),
    _b("1Cor", "1CO", "1 Corinthians", 16, "林前", "哥林多前书", True),
    _b("2Cor", "2CO", "2 Corinthians", 13, "林后", "哥林多后书", True),
    _b("Gal", "GAL", "Galatians", 6, "加", "加拉太书", True),
    _b("Eph", "EPH", "Ephesians", 6, "弗", "以弗所书", True),
    _b("Phil", "PHP", "Philippians", 4, "腓", "腓立比书", True),
    _b("Col", "COL", "Colossians", 4, "西", "歌罗西书", True),
    _b("1Thess", "1TH", "1 Thessalonians", 5, "帖前", "帖撒罗尼迦前书", True),
    _b("2Thess", "2TH", "2 Thessalonians", 3, "帖后", "帖撒罗尼迦后书", True),
    _b("1Tim", "1TI", "1 Timothy", 6, "提前", "提摩太前书", True),
    _b("2Tim", "2TI", "2 Timothy", 4, "提后", "提摩太后书", True),
    _b("Titus", "TIT", "Titus", 3, "多", "提多书", True),
    _b("Phlm", "PHM", "Philemon", 1, "门", "腓利门书", True),
    _b("Heb", "HEB", "Hebrews", 13, "来", "希伯来书", True),
    _b("Jas", "JAS", "James", 5, "雅", "雅各书", True),
    _b("1Pet", "1PE", "1 Peter", 5, "彼前", "彼得前书", True),
    _b("2Pet", "2PE", "2 Peter", 3, "彼后", "彼得后书", True),
    _b("1John", "1JN", "1 John", 5, "约一", "约翰一书", True),
    _b("2John", "2JN", "2 John", 1, "约二", "约翰二书", True),
    _b("3John", "3JN", "3 John", 1, "约三", "约翰三书", True),
    _b("Jude", "JUD", "Jude", 1, "犹", "犹大书", True),
    _b("Rev", "REV", "Revelation", 22, "启", "启示录", True),
]

BY_OSIS = {b.osis: b for b in BOOKS}
NT_BOOKS = [b for b in BOOKS if b.nt]
USFM_TO_OSIS = {b.usfm: b.osis for b in BOOKS}
# Masoretic-text chapter counts where they differ from English versification
WLC_CHAPTERS = {"Joel": 4, "Mal": 3}
# common abbreviations that are not prefixes of the English name
EXTRA_ALIASES = {
    "mt": "Matt", "mk": "Mark", "lk": "Luke", "jn": "John", "jhn": "John",
    "php": "Phil", "phm": "Phlm", "sos": "Song", "sng": "Song", "jas": "Jas",
    "1jn": "1John", "2jn": "2John", "3jn": "3John", "rv": "Rev",
}


class UnknownBook(ValueError):
    def __init__(self, query: str, suggestions: list[str]):
        self.query, self.suggestions = query, suggestions
        hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"Unknown book: {query!r}.{hint}")


def max_chapters(book: Book) -> int:
    return max(book.chapters, WLC_CHAPTERS.get(book.osis, 0))


def _norm(s: str) -> str:
    return s.replace(" ", "").replace("　", "").replace(".", "").lower()


def find_book(name: str) -> Book:
    q = _norm(name)
    if not q:
        raise UnknownBook(name, [])
    for b in BOOKS:
        if q in (_norm(b.osis), _norm(b.usfm), _norm(b.en)) or q in (b.zh_abbr, b.zh):
            return b
    if q in EXTRA_ALIASES:
        return BY_OSIS[EXTRA_ALIASES[q]]
    hits = [b for b in BOOKS if _norm(b.en).startswith(q) or _norm(b.osis).startswith(q)]
    uniq = {b.osis: b for b in hits}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    if uniq:
        raise UnknownBook(name, sorted(uniq))
    names = {_norm(b.en): b.osis for b in BOOKS}
    close = difflib.get_close_matches(q, names, n=3, cutoff=0.6)
    raise UnknownBook(name, [names[c] for c in close])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_canon.py -q
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/exeg/canon.py tests/test_canon.py
git commit -m "feat: canonical 66-book table with EN/中文 lookup"
```

---

### Task 3: Reference parsing

**Files:**
- Create: `src/exeg/refs.py`, `tests/test_refs.py`

**Interfaces:**
- Consumes: `canon.find_book`, `canon.max_chapters`, `canon.Book`
- Produces:
  - `Ref` frozen dataclass: `book: Book, chapter: int, verse: int | None, end_chapter: int, end_verse: int | None` (`verse is None` ⇒ whole chapter; then `end_verse is None` and `end_chapter == chapter`)
  - `parse_ref(s: str) -> Ref` — raises `BadRef(msg)` (a `ValueError`); `canon.UnknownBook` propagates
  - `Ref.contains(ch: int, v: int) -> bool`
  - `Ref.en_label() -> str` (e.g. `1 Peter 3:18–22`, en dash), `Ref.zh_label(full: bool = False) -> str` (e.g. `彼前 3:18–22` / `彼得前书 3:18–22`), `Ref.slug() -> str` (e.g. `1pet_3.18-22`, whole chapter `1pet_3`, cross-chapter `gen_1.28-2.3`)

- [ ] **Step 1: Write the failing test**

`tests/test_refs.py`:

```python
import pytest
from exeg.refs import BadRef, parse_ref

def test_basic_range():
    r = parse_ref("1Pet 3:18-22")
    assert (r.book.osis, r.chapter, r.verse, r.end_chapter, r.end_verse) == ("1Pet", 3, 18, 3, 22)

def test_spaced_name_and_en_dash():
    r = parse_ref("1 Peter 3:18–22")
    assert r.book.osis == "1Pet" and r.end_verse == 22

def test_chinese_ref_fullwidth_colon():
    r = parse_ref("彼前3：18-22")
    assert r.book.osis == "1Pet" and (r.chapter, r.verse, r.end_verse) == (3, 18, 22)

def test_single_verse():
    r = parse_ref("John 11:35")
    assert (r.chapter, r.verse, r.end_chapter, r.end_verse) == (11, 35, 11, 35)

def test_whole_chapter():
    r = parse_ref("诗 23")
    assert r.book.osis == "Ps" and r.chapter == 23 and r.verse is None

def test_cross_chapter():
    r = parse_ref("Gen 1:28-2:3")
    assert (r.chapter, r.verse, r.end_chapter, r.end_verse) == (1, 28, 2, 3)

def test_labels_and_slug():
    r = parse_ref("1Pet 3:18-22")
    assert r.en_label() == "1 Peter 3:18–22"
    assert r.zh_label() == "彼前 3:18–22"
    assert r.zh_label(full=True) == "彼得前书 3:18–22"
    assert r.slug() == "1pet_3.18-22"
    assert parse_ref("Ps 23").slug() == "ps_23"
    assert parse_ref("Gen 1:28-2:3").slug() == "gen_1.28-2.3"

def test_contains():
    r = parse_ref("Gen 1:28-2:3")
    assert r.contains(1, 30) and r.contains(2, 3) and not r.contains(2, 4)
    c = parse_ref("Ps 23")
    assert c.contains(23, 6) and not c.contains(24, 1)

def test_chapter_out_of_range():
    with pytest.raises(BadRef):
        parse_ref("1Pet 6:1")

def test_mt_versification_allowed():
    parse_ref("Joel 4:1")     # MT has 4 chapters

def test_backwards_range_rejected():
    with pytest.raises(BadRef):
        parse_ref("1Pet 3:22-18")

def test_garbage_rejected():
    with pytest.raises(BadRef):
        parse_ref("hello world")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_refs.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.refs`.

- [ ] **Step 3: Implement**

`src/exeg/refs.py`:

```python
"""Scripture reference parsing: '1Pet 3:18-22', '1 Peter 3:18–22', '彼前3：18-22'."""
import re
from dataclasses import dataclass

from exeg import canon


class BadRef(ValueError):
    pass


_TRANSLATE = str.maketrans({"：": ":", "–": "-", "—": "-", "~": "-", "－": "-", "　": " "})
_RANGE = re.compile(
    r"^(?P<book>.+?)\s*(?P<ch>\d+)\s*:\s*(?P<v1>\d+)"
    r"(?:\s*-\s*(?:(?P<ch2>\d+)\s*:\s*)?(?P<v2>\d+))?$"
)
_CHAPTER = re.compile(r"^(?P<book>.+?)\s*(?P<ch>\d+)$")


@dataclass(frozen=True)
class Ref:
    book: canon.Book
    chapter: int
    verse: int | None
    end_chapter: int
    end_verse: int | None

    def contains(self, ch: int, v: int) -> bool:
        if self.verse is None:
            return ch == self.chapter
        return (self.chapter, self.verse) <= (ch, v) <= (self.end_chapter, self.end_verse)

    def _span(self) -> str:
        if self.verse is None:
            return f"{self.chapter}"
        if (self.chapter, self.verse) == (self.end_chapter, self.end_verse):
            return f"{self.chapter}:{self.verse}"
        if self.chapter == self.end_chapter:
            return f"{self.chapter}:{self.verse}–{self.end_verse}"
        return f"{self.chapter}:{self.verse}–{self.end_chapter}:{self.end_verse}"

    def en_label(self) -> str:
        return f"{self.book.en} {self._span()}"

    def zh_label(self, full: bool = False) -> str:
        name = self.book.zh if full else self.book.zh_abbr
        return f"{name} {self._span()}"

    def slug(self) -> str:
        span = self._span().replace(":", ".").replace("–", "-")
        return f"{self.book.osis.lower()}_{span}"


def parse_ref(s: str) -> Ref:
    text = s.translate(_TRANSLATE).strip()
    m = _RANGE.match(text)
    if m:
        book = canon.find_book(m["book"])
        ch, v1 = int(m["ch"]), int(m["v1"])
        ch2 = int(m["ch2"]) if m["ch2"] else ch
        v2 = int(m["v2"]) if m["v2"] else v1
        ref = Ref(book, ch, v1, ch2, v2)
    else:
        m = _CHAPTER.match(text)
        if not m:
            raise BadRef(f"Cannot parse reference: {s!r} (expected forms like '1Pet 3:18-22', '彼前3:18-22', 'Ps 23')")
        book = canon.find_book(m["book"])
        ch = int(m["ch"])
        ref = Ref(book, ch, None, ch, None)
    limit = canon.max_chapters(ref.book)
    if not (1 <= ref.chapter <= limit and 1 <= ref.end_chapter <= limit):
        raise BadRef(f"{ref.book.en} has {limit} chapters; got chapter {max(ref.chapter, ref.end_chapter)}")
    if ref.verse is not None:
        if ref.verse < 1 or ref.end_verse < 1:
            raise BadRef("Verse numbers start at 1")
        if (ref.end_chapter, ref.end_verse) < (ref.chapter, ref.verse):
            raise BadRef(f"Range end {ref.end_chapter}:{ref.end_verse} precedes start {ref.chapter}:{ref.verse}")
    return ref
```

Note on `test_garbage_rejected`: "hello world" contains no digits, so both regexes fail → `BadRef` before any book lookup.

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_refs.py -q
```

Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/exeg/refs.py tests/test_refs.py
git commit -m "feat: EN/中文 scripture reference parsing"
```

---

### Task 4: Corpus storage

**Files:**
- Create: `src/exeg/corpus.py`, `tests/conftest.py`, `tests/test_corpus.py`

**Interfaces:**
- Consumes: `refs.Ref`, `canon.Book`
- Produces:
  - `root() -> Path` — `$EXEG_ROOT` or project root; `corpus_dir()`, `cache_dir()`, `sources_dir() -> Path` (create on demand)
  - `Verse` dataclass: `chapter: int, verse: int, text: str`
  - `Word` dataclass: `chapter: int, verse: int, idx: int, surface: str, lemma: str, strongs: str, morph: str`
  - `WORD_VERSIONS = {"sblgnt", "wlc"}`
  - `write_verses(version: str, osis: str, verses: list[Verse])`, `read_verses(version, osis) -> list[Verse]`
  - `write_words(version, osis, words: list[Word])`, `read_words(version, osis) -> list[Word]`
  - `has_version(version: str) -> bool`, `has_book(version: str, osis: str) -> bool`
  - `get_verses(version: str, ref: Ref) -> list[Verse]` — works for both text and word versions (joins word surfaces, stripping `/`); returns `[]` if book file missing
  - `get_words(ref: Ref, version: str) -> list[Word]` — words within ref range
- **File formats (source of truth):** text versions `data/corpus/{version}/{osis}.tsv` rows `chapter\tverse\ttext`; word versions rows `chapter\tverse\tidx\tsurface\tlemma\tstrongs\tmorph`. UTF-8, no header, tabs never appear inside fields.

- [ ] **Step 1: Write conftest fixture**

`tests/conftest.py`:

```python
import pytest

@pytest.fixture
def corpus_root(tmp_path, monkeypatch):
    monkeypatch.setenv("EXEG_ROOT", str(tmp_path))
    return tmp_path
```

- [ ] **Step 2: Write the failing test**

`tests/test_corpus.py`:

```python
from exeg import corpus
from exeg.corpus import Verse, Word
from exeg.refs import parse_ref

def test_root_uses_env(corpus_root):
    assert corpus.root() == corpus_root

def test_verse_roundtrip_and_range(corpus_root):
    vv = [Verse(3, v, f"text {v}") for v in range(16, 23)] + [Verse(4, 1, "next")]
    corpus.write_verses("web", "1Pet", vv)
    assert corpus.read_verses("web", "1Pet") == vv
    got = corpus.get_verses("web", parse_ref("1Pet 3:18-22"))
    assert [v.verse for v in got] == [18, 19, 20, 21, 22]
    assert corpus.get_verses("web", parse_ref("1Pet 3")) == vv[:-1]

def test_word_roundtrip_and_join(corpus_root):
    ww = [
        Word(3, 18, 1, "ὅτι", "ὅτι", "G3754", "C-/--------"),
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
    ]
    corpus.write_words("sblgnt", "1Pet", ww)
    assert corpus.read_words("sblgnt", "1Pet") == ww
    got = corpus.get_verses("sblgnt", parse_ref("1Pet 3:18"))
    assert got == [Verse(3, 18, "ὅτι Χριστὸς")]

def test_hebrew_segment_slash_stripped(corpus_root):
    ww = [Word(1, 1, 1, "בְּ/רֵאשִׁ֖ית", "b/7225", "H7225", "HR/Ncfsa")]
    corpus.write_words("wlc", "Gen", ww)
    assert corpus.get_verses("wlc", parse_ref("Gen 1:1"))[0].text == "בְּרֵאשִׁ֖ית"

def test_missing_book_returns_empty(corpus_root):
    assert corpus.get_verses("web", parse_ref("Jude 1:1")) == []
    assert not corpus.has_version("nasb95")

def test_get_words_range(corpus_root):
    ww = [Word(3, v, 1, f"w{v}", f"l{v}", "", "N-/----NSM-") for v in (17, 18, 19)]
    corpus.write_words("sblgnt", "1Pet", ww)
    got = corpus.get_words(parse_ref("1Pet 3:18-19"), "sblgnt")
    assert [w.verse for w in got] == [18, 19]
```

- [ ] **Step 3: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_corpus.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.corpus`.

- [ ] **Step 4: Implement**

`src/exeg/corpus.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_corpus.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/exeg/corpus.py tests/conftest.py tests/test_corpus.py
git commit -m "feat: plain-TSV corpus storage with word/verse records"
```

---

### Task 5: Minimal USFM parser

**Files:**
- Create: `src/exeg/usfm.py`, `tests/test_usfm.py`

**Interfaces:**
- Consumes: `corpus.Verse`
- Produces: `parse_usfm(text: str) -> tuple[str, list[Verse]]` — returns (USFM book code, verses). Raises `ValueError` if no `\id` line.

- [ ] **Step 1: Write the failing test**

`tests/test_usfm.py`:

```python
import pytest
from exeg.corpus import Verse
from exeg.usfm import parse_usfm

SAMPLE = r"""\id 1PE ebible.org
\h 1 Peter
\toc1 Peter's First Letter
\mt1 Peter's First Letter
\c 3
\s1 A heading to be skipped
\p
\v 18 Because Christ also suffered for sins once,\f + \fr 3:18 \ft Some manuscripts read.\f* the just for the unjust,
\q1 that he might bring you to God,
\v 19 in whom he also went and preached to the spirits in prison,
\c 4
\p
\v 1 Therefore, since Christ suffered \add for us\add* in the flesh, arm yourselves.
\v 2 He uses \w grace|strong="G5485"\w* daily.
"""

def test_parse_basic():
    code, verses = parse_usfm(SAMPLE)
    assert code == "1PE"
    assert verses[0] == Verse(3, 18, "Because Christ also suffered for sins once, the just for the unjust, that he might bring you to God,")
    assert verses[1] == Verse(3, 19, "in whom he also went and preached to the spirits in prison,")
    assert verses[2].chapter == 4 and verses[2].verse == 1
    assert "for us" in verses[2].text and "\\add" not in verses[2].text

def test_word_markup_keeps_text_drops_strongs():
    _, verses = parse_usfm(SAMPLE)
    assert verses[3].text == "He uses grace daily."

def test_bridged_verse_number():
    code, verses = parse_usfm("\\id OBA\n\\c 1\n\\v 1-2 Bridged text here.\n")
    assert verses == [Verse(1, 1, "Bridged text here.")]

def test_missing_id_raises():
    with pytest.raises(ValueError):
        parse_usfm("\\c 1\n\\v 1 no id line\n")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_usfm.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.usfm`.

- [ ] **Step 3: Implement**

`src/exeg/usfm.py`:

```python
"""Minimal USFM parser: extracts \\c/\\v verse text, strips notes and char markup."""
import re

from exeg.corpus import Verse

_ID = re.compile(r"\\id\s+([A-Z0-9]{3})")
_V = re.compile(r"\\v\s+(\d+)(?:[-–]\d+)?[ab]?\s*(.*)")
_MARKER_LINE = re.compile(r"\\\+?([a-z0-9]+)\s*(.*)")
# markers whose line content is NOT verse text
_SKIP = {
    "id", "ide", "usfm", "sts", "rem", "h", "toc1", "toc2", "toc3",
    "mt", "mt1", "mt2", "mt3", "ms", "ms1", "mr", "s", "s1", "s2", "s3",
    "r", "d", "sp", "cl", "cp", "cd", "b", "ib", "periph",
}
_NOTES = re.compile(r"\\[fx]\s.*?\\[fx]\*", re.S)
_W = re.compile(r"\\\+?w\s+([^|\\]*?)(?:\|[^\\]*?)?\\\+?w\*")
_RESIDUAL = re.compile(r"\\\+?[a-zA-Z0-9]+\*?")


def _clean(text: str) -> str:
    text = _NOTES.sub("", text)
    text = _W.sub(r"\1", text)
    text = _RESIDUAL.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_usfm(text: str) -> tuple[str, list[Verse]]:
    m = _ID.search(text)
    if not m:
        raise ValueError("USFM input has no \\id line")
    code = m.group(1)
    chapter = 0
    verses: list[Verse] = []
    cur: list | None = None  # [chapter, verse, [raw parts]]

    def flush():
        nonlocal cur
        if cur is not None:
            cleaned = _clean(" ".join(cur[2]))
            if cleaned:
                verses.append(Verse(cur[0], cur[1], cleaned))
        cur = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("\\c "):
            flush()
            chapter = int(line.split()[1])
            continue
        vm = _V.match(line)
        if vm:
            flush()
            cur = [chapter, int(vm.group(1)), [vm.group(2)]]
            continue
        mm = _MARKER_LINE.match(line)
        if mm:
            if mm.group(1) in _SKIP or cur is None:
                continue
            if mm.group(2):
                cur[2].append(mm.group(2))
            continue
        if cur is not None:
            cur[2].append(line)
    flush()
    return code, verses
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_usfm.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/exeg/usfm.py tests/test_usfm.py
git commit -m "feat: minimal USFM parser"
```

---

### Task 6: Fetch and normalize all open datasets (`exeg fetch`)

**Files:**
- Create: `src/exeg/fetch.py`, `tests/test_fetch.py`
- Modify: `src/exeg/cli.py` (register `fetch` subcommand)

**Interfaces:**
- Consumes: `canon.*`, `corpus.*`, `usfm.parse_usfm`
- Produces:
  - `normalize_sblgnt(text: str, lemma_map: dict[str, str]) -> list[Word]` (parses one MorphGNT book file)
  - `normalize_wlc(xml_text: str) -> list[Word]`
  - `parse_strongs_js(js_text: str) -> dict` and `build_greek_lemma_map(greek: dict) -> dict[str, str]`
  - `check_integrity() -> list[str]` (empty = healthy)
  - `cmd_fetch(args) -> int` — orchestrates strongs → sblgnt → wlc → ebible(web,kjv,cuvs) → integrity; `--only strongs,sblgnt,wlc,ebible` to subset; downloads skip existing files (idempotent/resumable)
  - `EBIBLE = {"web": "engwebp", "kjv": "eng-kjv", "cuvs": "cmn-cu89s"}`
  - Word field conventions this task locks in: SBLGNT `morph = f"{pos}/{parsing}"` (e.g. `V-/3AAI-S--`), `lemma` = MorphGNT col 7, `strongs` = `G####` via lemma map or `""`. WLC `lemma` = raw OSHB attr (e.g. `b/7225`), `strongs` = `H` + last digit-group, `morph` = raw OSHM (e.g. `HR/Ncfsa`).

- [ ] **Step 1: Write the failing test**

`tests/test_fetch.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_fetch.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.fetch`.

- [ ] **Step 3: Implement**

`src/exeg/fetch.py`:

```python
"""Download and normalize open datasets into the local corpus (exeg fetch)."""
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from exeg import canon, corpus
from exeg.corpus import Verse, Word
from exeg.usfm import parse_usfm

RAW = "https://raw.githubusercontent.com"
MORPHGNT_FILES = [  # (repo filename stem, verified 2026-07-19) — canonical NT order
    "61-Mt", "62-Mk", "63-Lk", "64-Jn", "65-Ac", "66-Ro", "67-1Co", "68-2Co",
    "69-Ga", "70-Eph", "71-Php", "72-Col", "73-1Th", "74-2Th", "75-1Ti",
    "76-2Ti", "77-Tit", "78-Phm", "79-Heb", "80-Jas", "81-1Pe", "82-2Pe",
    "83-1Jn", "84-2Jn", "85-3Jn", "86-Jud", "87-Re",
]
STRONGS_URLS = {
    "greek": f"{RAW}/openscriptures/strongs/master/greek/strongs-greek-dictionary.js",
    "hebrew": f"{RAW}/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js",
}
EBIBLE = {"web": "engwebp", "kjv": "eng-kjv", "cuvs": "cmn-cu89s"}
_OSIS_NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"


def download(url: str, dest, force: bool = False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "exeg/0.1 (personal study tool)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def parse_strongs_js(js_text: str) -> dict:
    return json.loads(js_text[js_text.index("{"): js_text.rindex("}") + 1])


def build_greek_lemma_map(greek: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for code in sorted(greek, key=lambda c: int(c[1:])):
        lemma = unicodedata.normalize("NFC", greek[code].get("lemma", "") or "")
        if lemma:
            out.setdefault(lemma, code)
    return out


def normalize_sblgnt(text: str, lemma_map: dict[str, str]) -> list[Word]:
    words: list[Word] = []
    idx, prev = 0, None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 7:
            continue
        bcv, pos, parsing, surface, _word, _norm, lemma = parts
        ch, v = int(bcv[2:4]), int(bcv[4:6])
        idx = idx + 1 if prev == (ch, v) else 1
        prev = (ch, v)
        strongs = lemma_map.get(unicodedata.normalize("NFC", lemma), "")
        words.append(Word(ch, v, idx, surface, lemma, strongs, f"{pos}/{parsing}"))
    return words


def normalize_wlc(xml_text: str) -> list[Word]:
    root = ET.fromstring(xml_text)
    words: list[Word] = []
    for velem in root.iter(f"{_OSIS_NS}verse"):
        osis_id = velem.get("osisID", "")
        try:
            _, ch, v = osis_id.rsplit(".", 2)
        except ValueError:
            continue
        idx = 0
        for w in velem:
            if w.tag != f"{_OSIS_NS}w":
                continue
            idx += 1
            lemma = w.get("lemma", "")
            nums = re.findall(r"\d+", lemma)
            strongs = f"H{nums[-1]}" if nums else ""
            surface = "".join(w.itertext()).strip()
            words.append(Word(int(ch), int(v), idx, surface, lemma, strongs, w.get("morph", "")))
    return words


def fetch_strongs(log=print) -> dict[str, str]:
    out_dir = corpus.corpus_dir() / "strongs"
    out_dir.mkdir(parents=True, exist_ok=True)
    lemma_map: dict[str, str] = {}
    for lang, url in STRONGS_URLS.items():
        src = download(url, corpus.sources_dir() / f"strongs-{lang}.js")
        data = parse_strongs_js(src.read_text(encoding="utf-8"))
        (out_dir / f"{lang}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        log(f"strongs/{lang}: {len(data)} entries")
        if lang == "greek":
            lemma_map = build_greek_lemma_map(data)
            (out_dir / "greek-lemma-map.json").write_text(
                json.dumps(lemma_map, ensure_ascii=False), encoding="utf-8")
    return lemma_map


def load_greek_lemma_map() -> dict[str, str]:
    path = corpus.corpus_dir() / "strongs" / "greek-lemma-map.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fetch_sblgnt(log=print) -> None:
    lemma_map = load_greek_lemma_map()
    for stem, book in zip(MORPHGNT_FILES, canon.NT_BOOKS):
        url = f"{RAW}/morphgnt/sblgnt/master/{stem}-morphgnt.txt"
        src = download(url, corpus.sources_dir() / "sblgnt" / f"{stem}-morphgnt.txt")
        corpus.write_words("sblgnt", book.osis, normalize_sblgnt(src.read_text(encoding="utf-8"), lemma_map))
        log(f"sblgnt/{book.osis} done")


def fetch_wlc(log=print) -> None:
    for book in canon.BOOKS:
        if book.nt:
            continue
        url = f"{RAW}/openscriptures/morphhb/master/wlc/{book.osis}.xml"
        src = download(url, corpus.sources_dir() / "wlc" / f"{book.osis}.xml")
        corpus.write_words("wlc", book.osis, normalize_wlc(src.read_text(encoding="utf-8")))
        log(f"wlc/{book.osis} done")


def fetch_ebible(log=print) -> None:
    for version, tid in EBIBLE.items():
        zpath = download(f"https://ebible.org/Scriptures/{tid}_usfm.zip",
                         corpus.sources_dir() / f"{tid}_usfm.zip")
        out = corpus.sources_dir() / tid
        out.mkdir(exist_ok=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out)
        count = 0
        for f in sorted(out.rglob("*")):
            if f.suffix.lower() not in (".usfm", ".sfm"):
                continue
            try:
                code, verses = parse_usfm(f.read_text(encoding="utf-8-sig"))
            except ValueError:
                continue
            osis = canon.USFM_TO_OSIS.get(code)
            if osis and verses:
                corpus.write_verses(version, osis, verses)
                count += 1
        log(f"{version}: {count} books")


def check_integrity() -> list[str]:
    problems: list[str] = []
    cdir = corpus.corpus_dir()
    if not cdir.is_dir():
        return ["corpus is empty — run `exeg fetch`"]
    for vdir in sorted(cdir.iterdir()):
        version = vdir.name
        if version == "strongs" or not vdir.is_dir():
            continue
        for tsv in sorted(vdir.glob("*.tsv")):
            osis = tsv.stem
            book = canon.BY_OSIS.get(osis)
            if not book:
                problems.append(f"{version}/{osis}: unknown book file")
                continue
            rows = (corpus.read_words(version, osis) if version in corpus.WORD_VERSIONS
                    else corpus.read_verses(version, osis))
            chapters = sorted({r.chapter for r in rows})
            expected = canon.WLC_CHAPTERS.get(osis, book.chapters) if version == "wlc" else book.chapters
            if chapters != list(range(1, expected + 1)):
                problems.append(f"{version}/{osis}: chapters {chapters[:3]}…{chapters[-3:] if len(chapters) > 3 else ''} "
                                f"!= 1..{expected}")
    return problems


def cmd_fetch(args) -> int:
    only = set(args.only.split(",")) if args.only else {"strongs", "sblgnt", "wlc", "ebible"}
    if "strongs" in only:
        fetch_strongs()
    if "sblgnt" in only:
        fetch_sblgnt()
    if "wlc" in only:
        fetch_wlc()
    if "ebible" in only:
        fetch_ebible()
    problems = check_integrity()
    for p in problems:
        print(f"INTEGRITY: {p}")
    print("fetch complete" + (f" — {len(problems)} problems" if problems else ", corpus healthy"))
    return 1 if problems else 0
```

- [ ] **Step 4: Register the subcommand**

In `src/exeg/cli.py`, replace the `p.add_subparsers(dest="command")` line in `build_parser` with:

```python
    sub = p.add_subparsers(dest="command")

    from exeg import fetch as _fetch
    f = sub.add_parser("fetch", help="download and normalize all datasets")
    f.add_argument("--only", help="comma list: strongs,sblgnt,wlc,ebible")
    f.set_defaults(func=_fetch.cmd_fetch)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_fetch.py tests/test_cli.py -q
```

Expected: `7 passed` (5 fetch + 2 cli).

- [ ] **Step 6: Real fetch smoke test (network; ~1–2 min; NOT part of pytest)**

```bash
.venv/bin/exeg fetch
.venv/bin/exeg fetch   # second run must be fast (downloads skipped) and print "corpus healthy"
ls data/corpus         # expect: cuvs kjv sblgnt strongs web wlc
grep -c $'\t' data/corpus/sblgnt/1Pet.tsv   # expect ~1680 (word rows)
```

Expected: both runs end with `fetch complete, corpus healthy`. If a specific book fails integrity, read the INTEGRITY line and fix the relevant normalizer — do not delete the check.

- [ ] **Step 7: Commit**

```bash
git add src/exeg/fetch.py src/exeg/cli.py tests/test_fetch.py
git commit -m "feat: exeg fetch — download/normalize SBLGNT, WLC, ebible, Strong's"
```

---

### Task 7: Parallel passage display (`exeg passage`)

**Files:**
- Create: `src/exeg/display.py`, `tests/test_display.py`
- Modify: `src/exeg/cli.py`

**Interfaces:**
- Consumes: `corpus.get_verses/has_version`, `refs.Ref`
- Produces:
  - `LABELS = {"sblgnt": "SBLGNT", "wlc": "WLC", "esv": "ESV", "nasb95": "NASB95", "cuvs": "和合本", "web": "WEB", "kjv": "KJV"}`
  - `default_versions(book: Book) -> list[str]` — `["sblgnt"|"wlc", "esv", "nasb95", "cuvs"]`
  - `gather(ref: Ref, versions: list[str]) -> tuple[dict[str, dict[tuple[int, int], str]], list[str]]` — per-version verse texts + human-readable notes for unavailable versions. In this task only local corpus versions are wired; `esv`/`nasb95` produce the note `"{LABEL} unavailable — set {KEY} or run `exeg fetch`/`exeg import`"`. Tasks 8–9 replace those two branches.
  - `render(ref: Ref, versions: list[str] | None = None) -> str`
  - `cmd_passage(args) -> int`
- Render format (locked): optional `> note` lines, then per verse `### {en} {ch}:{v} · {zh_abbr} {ch}:{v}` and one `- **{LABEL}** {text}` per version, with `- **{LABEL}** [not in {LABEL}]` when the version lacks that verse but has the book, and the version omitted entirely when it lacks the whole book's testament? No — always listed; honesty over tidiness.

- [ ] **Step 1: Write the failing test**

`tests/test_display.py`:

```python
from exeg import corpus, display
from exeg.corpus import Verse, Word
from exeg.refs import parse_ref

def seed(corpus_root):
    corpus.write_words("sblgnt", "1Pet", [
        Word(3, 18, 1, "ὅτι", "ὅτι", "G3754", "C-/--------"),
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
        Word(3, 19, 1, "ἐν", "ἐν", "G1722", "P-/--------"),
    ])
    corpus.write_verses("cuvs", "1Pet", [Verse(3, 18, "因基督也曾一次为罪受苦"), Verse(3, 19, "他借这灵曾去传道")])
    corpus.write_verses("web", "1Pet", [Verse(3, 18, "Because Christ also suffered for sins once")])

def test_render_parallel(corpus_root):
    seed(corpus_root)
    out = display.render(parse_ref("1Pet 3:18-19"), ["sblgnt", "web", "cuvs"])
    assert "### 1 Peter 3:18 · 彼前 3:18" in out
    assert "- **SBLGNT** ὅτι Χριστὸς" in out
    assert "- **和合本** 因基督也曾一次为罪受苦" in out
    # web lacks v19 -> explicit marker, not silent skip
    assert "- **WEB** [not in WEB]" in out

def test_unavailable_api_version_noted(corpus_root):
    seed(corpus_root)
    out = display.render(parse_ref("1Pet 3:18"), ["esv", "cuvs"])
    assert "> ESV unavailable" in out
    assert "- **和合本**" in out

def test_default_versions(corpus_root):
    from exeg.canon import BY_OSIS
    assert display.default_versions(BY_OSIS["1Pet"])[0] == "sblgnt"
    assert display.default_versions(BY_OSIS["Gen"])[0] == "wlc"

def test_cli_passage(corpus_root, capsys):
    seed(corpus_root)
    from exeg.cli import main
    assert main(["passage", "彼前3:18", "--versions", "sblgnt,cuvs"]) == 0
    out = capsys.readouterr().out
    assert "ὅτι Χριστὸς" in out and "因基督" in out

def test_cli_bad_ref_message(corpus_root, capsys):
    from exeg.cli import main
    assert main(["passage", "Filippians 1:1"]) == 1
    assert "Did you mean" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_display.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.display`.

- [ ] **Step 3: Implement**

`src/exeg/display.py`:

```python
"""Parallel passage rendering (exeg passage)."""
from exeg import corpus
from exeg.canon import Book
from exeg.refs import Ref

LABELS = {"sblgnt": "SBLGNT", "wlc": "WLC", "esv": "ESV", "nasb95": "NASB95",
          "cuvs": "和合本", "web": "WEB", "kjv": "KJV"}


def default_versions(book: Book) -> list[str]:
    return [("sblgnt" if book.nt else "wlc"), "esv", "nasb95", "cuvs"]


def _api_texts(version: str, ref: Ref) -> dict[tuple[int, int], str]:
    """ESV/NASB95 via APIs — wired in Tasks 8 and 9. Local corpus wins if present."""
    raise LookupError(
        f"{LABELS[version]} unavailable — "
        + ("set ESV_API_KEY in .env" if version == "esv"
           else "set API_BIBLE_KEY in .env or run `exeg import`"))


def gather(ref: Ref, versions: list[str]):
    texts: dict[str, dict[tuple[int, int], str]] = {}
    notes: list[str] = []
    for version in versions:
        if version in ("esv", "nasb95") and not corpus.has_version(version):
            try:
                texts[version] = _api_texts(version, ref)
            except LookupError as e:
                notes.append(str(e))
            continue
        texts[version] = {(v.chapter, v.verse): v.text for v in corpus.get_verses(version, ref)}
    return texts, notes


def render(ref: Ref, versions: list[str] | None = None) -> str:
    versions = versions or default_versions(ref.book)
    texts, notes = gather(ref, versions)
    ids = sorted({vid for tv in texts.values() for vid in tv})
    lines: list[str] = [f"> {n}" for n in notes]
    if not ids:
        lines.append(f"> no local text found for {ref.en_label()} — run `exeg fetch`")
    for ch, v in ids:
        lines.append("")
        lines.append(f"### {ref.book.en} {ch}:{v} · {ref.book.zh_abbr} {ch}:{v}")
        for version in versions:
            if version not in texts:
                continue
            label = LABELS.get(version, version.upper())
            text = texts[version].get((ch, v))
            lines.append(f"- **{label}** {text if text else f'[not in {label}]'}")
    return "\n".join(lines).strip() + "\n"


def cmd_passage(args) -> int:
    import sys
    from exeg import canon, refs
    try:
        ref = refs.parse_ref(args.ref)
    except (refs.BadRef, canon.UnknownBook) as e:
        print(str(e), file=sys.stderr)
        return 1
    versions = args.versions.split(",") if args.versions else None
    print(render(ref, versions))
    return 0
```

- [ ] **Step 4: Register the subcommand**

In `src/exeg/cli.py` `build_parser`, after the `fetch` block add:

```python
    from exeg import display as _display
    pp = sub.add_parser("passage", help="print a passage in parallel versions")
    pp.add_argument("ref", help="e.g. '1Pet 3:18-22' or '彼前3:18-22'")
    pp.add_argument("--versions", help="comma list, e.g. sblgnt,esv,cuvs")
    pp.set_defaults(func=_display.cmd_passage)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_display.py -q
```

Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/exeg/display.py src/exeg/cli.py tests/test_display.py
git commit -m "feat: exeg passage — parallel bilingual display"
```

---

### Task 8: ESV API client with capped cache

**Files:**
- Create: `src/exeg/esv.py`, `tests/test_esv.py`
- Modify: `src/exeg/display.py` (`_api_texts` esv branch)

**Interfaces:**
- Consumes: `corpus.cache_dir`, `refs.Ref`
- Produces:
  - `class Unavailable(Exception)` — message is user-displayable
  - `get_passage(ref: Ref) -> dict[tuple[int, int], str]` — cache-first; on miss calls Crossway API; raises `Unavailable` when no key / HTTP failure and cache cannot satisfy
  - `_http_json(url: str, headers: dict) -> dict` — module-level, monkeypatched in tests
  - `NOTICE = "Scripture quotations marked “ESV” are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway. Used by permission. All rights reserved."`
  - Cache file `data/cache/esv.json`: `{"verses": {"1Pet.3.18": {"t": "...", "at": 1721360000.0}}, "chapters": ["Ps.23"]}`, ≤ 500 verse entries, oldest-`at` evicted.
- API (v3): `GET https://api.esv.org/v3/passage/text/?q=1+Peter+3:18-22&include-passage-references=false&include-verse-numbers=true&include-first-verse-numbers=true&include-footnotes=false&include-headings=false&include-short-copyright=false`, header `Authorization: Token $ESV_API_KEY`. Response: `{"passages": ["[18] For Christ also suffered once... [19] ..."], ...}`. Verse markers `[n]`; a marker ≤ the previous one means chapter rollover (cross-chapter queries).

- [ ] **Step 1: Write the failing test**

`tests/test_esv.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_esv.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.esv`.

- [ ] **Step 3: Implement**

`src/exeg/esv.py`:

```python
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
        for k in sorted(vs, key=lambda k: vs[k]["at"])[: len(vs) - CAP]:
            del vs[k]
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
    wanted = [(ch, v) for ch in range(ref.chapter, ref.end_chapter + 1)
              for v in range(1, 200)
              if ref.contains(ch, v) and _key(osis, ch, v) in cache["verses"]]
    # cache satisfies only if every explicitly requested verse of a same-chapter range is present;
    # for cross-chapter ranges we cannot know middle-chapter lengths, so require an API round trip
    if ref.chapter == ref.end_chapter:
        need = [(ref.chapter, v) for v in range(ref.verse, ref.end_verse + 1)]
        if all(_key(osis, ch, v) in cache["verses"] for ch, v in need):
            return {(ch, v): cache["verses"][_key(osis, ch, v)]["t"] for ch, v in need}
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
```

- [ ] **Step 4: Wire into display**

In `src/exeg/display.py`, replace the whole `_api_texts` function with:

```python
def _api_texts(version: str, ref: Ref) -> dict[tuple[int, int], str]:
    """ESV via Crossway API; NASB95 wired in Task 9. Local corpus wins if present."""
    if version == "esv":
        from exeg import esv
        try:
            return esv.get_passage(ref)
        except esv.Unavailable as e:
            raise LookupError(str(e)) from e
    raise LookupError(f"{LABELS[version]} unavailable — set API_BIBLE_KEY in .env or run `exeg import`")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_esv.py tests/test_display.py -q
```

Expected: `10 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/exeg/esv.py src/exeg/display.py tests/test_esv.py
git commit -m "feat: ESV API client with license-capped cache"
```

---

### Task 9: NASB95 via API.Bible

**Files:**
- Create: `src/exeg/apibible.py`, `tests/test_apibible.py`
- Modify: `src/exeg/display.py` (`_api_texts` nasb95 branch)

**Interfaces:**
- Consumes: `corpus.cache_dir`, `refs.Ref`, `canon.Book.usfm`
- Produces:
  - `class Unavailable(Exception)`
  - `get_passage(ref: Ref) -> dict[tuple[int, int], str]` — same contract as `esv.get_passage`
  - `_http_json(url: str, key: str) -> dict` — monkeypatched in tests
  - `NOTICE = "Scripture quotations taken from the NASB® New American Standard Bible®, Copyright © 1960, 1971, 1977, 1995 by The Lockman Foundation. Used by permission. All rights reserved. lockman.org"`
  - Cache `data/cache/nasb95.json` — same shape/cap as ESV cache, plus `"bible_id"` and `"chapter_verses": {"1PE.3": ["1PE.3.1", ...]}`.
- API: base `https://api.scripture.api.bible/v1`, header `api-key: $API_BIBLE_KEY`. Endpoints used: `GET /bibles?language=eng` (find id where `"NASB" in abbreviation/abbreviationLocal`, prefer `"1995" in name`, else first NASB; none → `Unavailable` suggesting `exeg import`); `GET /bibles/{id}/chapters/{USFM}.{ch}/verses` (verse-id list); `GET /bibles/{id}/verses/{vid}?content-type=text&include-notes=false&include-titles=false&include-verse-numbers=false` (single verse; text in `data.content`, strip a leading number if present).

- [ ] **Step 1: Write the failing test**

`tests/test_apibible.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_apibible.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.apibible`.

- [ ] **Step 3: Implement**

`src/exeg/apibible.py`:

```python
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
```

- [ ] **Step 4: Wire into display**

In `src/exeg/display.py`, replace `_api_texts` again, final form:

```python
def _api_texts(version: str, ref: Ref) -> dict[tuple[int, int], str]:
    """Copyrighted versions come from official APIs; a locally imported copy wins (checked in gather)."""
    if version == "esv":
        from exeg import esv as mod
    else:
        from exeg import apibible as mod
    try:
        return mod.get_passage(ref)
    except mod.Unavailable as e:
        raise LookupError(str(e)) from e
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass (no failures across the suite).

- [ ] **Step 6: Commit**

```bash
git add src/exeg/apibible.py src/exeg/display.py tests/test_apibible.py
git commit -m "feat: NASB95 via API.Bible with capped cache"
```

---

### Task 10: Import user-licensed translations (`exeg import`)

**Files:**
- Create: `src/exeg/importer.py`, `tests/test_importer.py`
- Modify: `src/exeg/cli.py`

**Interfaces:**
- Consumes: `usfm.parse_usfm`, `refs.parse_ref`, `corpus.write_verses`
- Produces:
  - `import_path(path: Path, version: str, fmt: str | None = None, log=print) -> int` — returns number of books written; raises `SystemExit` with message on unusable input. `fmt` in `{"usfm", "tsv", None}` (None = detect: `.usfm`/`.sfm` or directory → usfm, else tsv)
  - TSV import format (documented in AGENTS.md): one verse per line, `REF<TAB>text`, REF any single-verse form `parse_ref` accepts, e.g. `1Pet 3:18\tFor Christ also died...`
  - `cmd_import(args) -> int`

- [ ] **Step 1: Write the failing test**

`tests/test_importer.py`:

```python
import pytest
from exeg import corpus, importer
from exeg.refs import parse_ref

def test_import_tsv(corpus_root, tmp_path):
    src = tmp_path / "nasb.tsv"
    src.write_text("1Pet 3:18\tFor Christ also died for sins once for all\n"
                   "1Pet 3:19\tin which also He went\n"
                   "彼前 4:1\tmixed-ref-style line\n", encoding="utf-8")
    n = importer.import_path(src, "nasb95", log=lambda *a: None)
    assert n == 1
    got = corpus.get_verses("nasb95", parse_ref("1Pet 3:18-19"))
    assert [v.verse for v in got] == [18, 19]
    assert corpus.get_verses("nasb95", parse_ref("1Pet 4:1"))[0].text == "mixed-ref-style line"

def test_import_usfm_dir(corpus_root, tmp_path):
    d = tmp_path / "mod"
    d.mkdir()
    (d / "1pe.usfm").write_text("\\id 1PE\n\\c 3\n\\v 18 For Christ also died.\n", encoding="utf-8")
    (d / "jud.usfm").write_text("\\id JUD\n\\c 1\n\\v 1 Jude, a bond-servant.\n", encoding="utf-8")
    n = importer.import_path(d, "nasb95", log=lambda *a: None)
    assert n == 2
    assert corpus.has_book("nasb95", "Jude")

def test_bad_tsv_line_reported(corpus_root, tmp_path):
    src = tmp_path / "bad.tsv"
    src.write_text("not a reference\tsome text\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        importer.import_path(src, "nasb95", log=lambda *a: None)

def test_cli_import(corpus_root, tmp_path, capsys):
    src = tmp_path / "n.tsv"
    src.write_text("John 11:35\tJesus wept.\n", encoding="utf-8")
    from exeg.cli import main
    assert main(["import", str(src), "--version", "nasb95"]) == 0
    assert corpus.has_version("nasb95")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_importer.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.importer`.

- [ ] **Step 3: Implement**

`src/exeg/importer.py`:

```python
"""Import a user-licensed translation into the local corpus (exeg import).

The imported text stays inside data/ (gitignored) and is never redistributed.
"""
import sys
from pathlib import Path

from exeg import canon, corpus, refs, usfm


def _import_usfm_files(files: list[Path], version: str, log) -> int:
    count = 0
    for f in sorted(files):
        try:
            code, verses = usfm.parse_usfm(f.read_text(encoding="utf-8-sig"))
        except ValueError as e:
            log(f"skip {f.name}: {e}")
            continue
        osis = canon.USFM_TO_OSIS.get(code)
        if not osis:
            log(f"skip {f.name}: book code {code} not in the 66-book canon")
            continue
        if verses:
            corpus.write_verses(version, osis, verses)
            log(f"{version}/{osis}: {len(verses)} verses")
            count += 1
    return count


def _import_tsv(path: Path, version: str, log) -> int:
    books: dict[str, list[corpus.Verse]] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        if "\t" not in line:
            raise SystemExit(f"{path.name}:{lineno}: expected 'REF<TAB>text'")
        ref_s, text = line.split("\t", 1)
        try:
            ref = refs.parse_ref(ref_s.strip())
        except (refs.BadRef, canon.UnknownBook) as e:
            raise SystemExit(f"{path.name}:{lineno}: {e}") from e
        if ref.verse is None or (ref.chapter, ref.verse) != (ref.end_chapter, ref.end_verse):
            raise SystemExit(f"{path.name}:{lineno}: one single-verse reference per line, got {ref_s!r}")
        books.setdefault(ref.book.osis, []).append(corpus.Verse(ref.chapter, ref.verse, text.strip()))
    for osis, verses in books.items():
        verses.sort(key=lambda v: (v.chapter, v.verse))
        corpus.write_verses(version, osis, verses)
        log(f"{version}/{osis}: {len(verses)} verses")
    return len(books)


def import_path(path: Path, version: str, fmt: str | None = None, log=print) -> int:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"not found: {path}")
    if fmt is None:
        fmt = "usfm" if path.is_dir() or path.suffix.lower() in (".usfm", ".sfm") else "tsv"
    if fmt == "usfm":
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        files = [f for f in files if f.suffix.lower() in (".usfm", ".sfm")]
        if not files:
            raise SystemExit(f"no .usfm/.sfm files under {path}")
        n = _import_usfm_files(files, version, log)
    else:
        n = _import_tsv(path, version, log)
    if n == 0:
        raise SystemExit("nothing imported")
    log(f"imported {n} book(s) into data/corpus/{version}/ "
        "(local only, gitignored — your licensed copy is never redistributed)")
    return n


def cmd_import(args) -> int:
    import_path(Path(args.path), args.version, args.format)
    return 0
```

- [ ] **Step 4: Register the subcommand**

In `src/exeg/cli.py` `build_parser`, after the `passage` block add:

```python
    from exeg import importer as _importer
    ip = sub.add_parser("import", help="import a user-licensed translation (kept local)")
    ip.add_argument("path", help="a .usfm/.sfm file, a directory of them, or a REF<TAB>text .tsv")
    ip.add_argument("--version", required=True, help="corpus version name, e.g. nasb95")
    ip.add_argument("--format", choices=["usfm", "tsv"], help="override detection")
    ip.set_defaults(func=_importer.cmd_import)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_importer.py -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/exeg/importer.py src/exeg/cli.py tests/test_importer.py
git commit -m "feat: exeg import for user-licensed translations"
```

---

### Task 11: Search and word study (`exeg search`, `exeg word`)

**Files:**
- Create: `src/exeg/search.py`, `tests/test_search.py`
- Modify: `src/exeg/cli.py`

**Interfaces:**
- Consumes: `corpus.*`, `canon.*`, Strong's JSONs written by Task 6 (`data/corpus/strongs/{greek,hebrew}.json`, `greek-lemma-map.json`)
- Produces:
  - `search_text(pattern: str, versions: list[str], book: str | None = None, lemma: bool = False) -> list[tuple[str, str, int, int, str]]` — `(version, osis, ch, v, text)`; regex, case-insensitive; `lemma=True` matches the lemma column of word versions instead of verse text
  - `word_occurrences(query: str) -> dict` — `{"query", "strongs", "lemma", "gloss", "occurrences": [(version, osis, ch, v, surface, morph)], "by_book": {osis: count}}`; query is `G####`/`H####` (case-insensitive) or a lemma (NFC-matched)
  - `greek_morph_label(morph: str) -> str` — decodes SBLGNT `pos/parsing` (e.g. `V-/3AAI-S--` → `aorist active indicative 3sg`, `N-/----NSF-` → `nom sg f`); non-Greek/undecodable → raw code
  - `cmd_search(args) -> int`, `cmd_word(args) -> int`

- [ ] **Step 1: Write the failing test**

`tests/test_search.py`:

```python
import json
from exeg import corpus, search
from exeg.corpus import Verse, Word

def seed(corpus_root):
    corpus.write_verses("web", "1Pet", [
        Verse(1, 3, "has begotten us again to a living hope"),
        Verse(2, 24, "who his own self bore our sins"),
    ])
    corpus.write_words("sblgnt", "1Pet", [
        Word(2, 21, 1, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 18, 1, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
    ])
    sdir = corpus.corpus_dir() / "strongs"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "greek.json").write_text(json.dumps(
        {"G3958": {"lemma": "πάσχω", "strongs_def": "to experience a sensation, suffer"}}), encoding="utf-8")
    (sdir / "greek-lemma-map.json").write_text(json.dumps({"πάσχω": "G3958"}), encoding="utf-8")
    (sdir / "hebrew.json").write_text("{}", encoding="utf-8")

def test_search_text(corpus_root):
    seed(corpus_root)
    hits = search.search_text("living hope", ["web"])
    assert hits == [("web", "1Pet", 1, 3, "has begotten us again to a living hope")]

def test_search_lemma(corpus_root):
    seed(corpus_root)
    hits = search.search_text("πάσχω", ["sblgnt"], lemma=True)
    assert [(h[2], h[3]) for h in hits] == [(2, 21), (3, 18)]

def test_word_by_strongs_and_lemma(corpus_root):
    seed(corpus_root)
    for q in ("G3958", "g3958", "πάσχω"):
        r = search.word_occurrences(q)
        assert r["strongs"] == "G3958" and r["lemma"] == "πάσχω"
        assert "suffer" in r["gloss"]
        assert r["by_book"] == {"1Pet": 2}

def test_morph_label():
    assert search.greek_morph_label("V-/3AAI-S--") == "aorist active indicative 3sg"
    assert search.greek_morph_label("N-/----NSF-") == "nom sg f"
    assert search.greek_morph_label("HVqp3ms") == "HVqp3ms"   # Hebrew stays raw

def test_cli(corpus_root, capsys):
    seed(corpus_root)
    from exeg.cli import main
    assert main(["search", "living hope", "--versions", "web"]) == 0
    assert "1Pet 1:3" in capsys.readouterr().out
    assert main(["word", "G3958"]) == 0
    out = capsys.readouterr().out
    assert "πάσχω" in out and "2×" in out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_search.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.search`.

- [ ] **Step 3: Implement**

`src/exeg/search.py`:

```python
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
        print(f"{version:7s} {canon.BY_OSIS[osis].en} {ch}:{v}  {text}")
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
        print(f"  {canon.BY_OSIS[osis].en}: {n}×")
    for version, osis, ch, v, surface, morph in r["occurrences"][: args.limit]:
        print(f"  {canon.BY_OSIS[osis].en} {ch}:{v}  {surface}  ({greek_morph_label(morph)})")
    return 0
```

- [ ] **Step 4: Register the subcommands**

In `src/exeg/cli.py` `build_parser`, after the `import` block add:

```python
    from exeg import search as _search
    sp = sub.add_parser("search", help="search the corpus (regex)")
    sp.add_argument("pattern")
    sp.add_argument("--versions", help="comma list (default web,kjv,cuvs; with --lemma: sblgnt,wlc)")
    sp.add_argument("--book", help="restrict to one book")
    sp.add_argument("--lemma", action="store_true", help="match lemmas in Greek/Hebrew corpora")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=_search.cmd_search)

    wp = sub.add_parser("word", help="word study: occurrences of a Strong's number or lemma")
    wp.add_argument("query", help="G3958, H1254, or a lemma like πάσχω")
    wp.add_argument("--limit", type=int, default=30)
    wp.set_defaults(func=_search.cmd_word)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_search.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/exeg/search.py src/exeg/cli.py tests/test_search.py
git commit -m "feat: exeg search and exeg word"
```

---

### Task 12: Study-file scaffold (`exeg scaffold`)

**Files:**
- Create: `src/exeg/scaffold.py`, `tests/test_scaffold.py`
- Modify: `src/exeg/cli.py`

**Interfaces:**
- Consumes: `display.gather/LABELS/default_versions`, `search.greek_morph_label/word_occurrences/_strongs_dicts`, `corpus.get_words`, `esv.NOTICE`, `apibible.NOTICE`
- Produces:
  - `pick_words(ref: Ref) -> list[Word]` — from the original-language corpus for the ref's testament: keep POS ∈ {V, N, A}; drop stoplist lemmas; dedupe by lemma (first occurrence wins); cap 10. Greek POS = `morph[0]`; Hebrew POS = first letter of the morph segment aligned with the digit-bearing lemma segment (see code).
  - `GREEK_STOP = {"εἰμί", "λέγω", "ἔχω", "γίνομαι"}`, `HEBREW_STOP = {"H1961", "H559", "H6213"}` (compared against `Word.strongs`)
  - `build(ref: Ref, versions: list[str] | None = None, today: str | None = None) -> str` — the complete study-file markdown
  - `write(ref: Ref, force: bool = False) -> Path` — writes to `studies/{ref.slug()}.md`; existing file without `force` → `SystemExit`
  - `cmd_scaffold(args) -> int`
- Output layout is **exactly** (spec-locked headings):

```
# {en_label} · {zh_label(full=True)}
> scaffolded {YYYY-MM-DD} · {labels joined with " | "}

## Text · 经文对照
{one "### {en} {ch}:{v} · {zh_abbr} {ch}:{v}" block per verse, lines "- **LABEL** text",
 preceded by "> note" lines for unavailable versions}

## Word Studies · 字词研究
{per picked word:}
### {lemma} ({surface}, v. {v}) — {strongs or "?"} · {morph label}
gloss: {gloss or "—"} · in {book.en}: {n}× ({refs list, max 12, "…" if more})
（your analysis · 你的分析）

## Structure & Context · 结构与背景
- Literary structure · 文学结构：
- Historical setting · 历史背景：
- Place in the book's argument · 在全书论证中的位置：

## Interpretation · 释经结论

## Theology & Application · 神学综合与应用
- Cross-references · 串珠：

---
{esv.NOTICE if ESV text present}
{apibible.NOTICE if NASB95 API text present}
SBLGNT: © 2010 Society of Biblical Literature and Logos Bible Software.
```

- [ ] **Step 1: Write the failing test**

`tests/test_scaffold.py`:

```python
import json
import pytest
from exeg import corpus, scaffold
from exeg.corpus import Verse, Word
from exeg.refs import parse_ref

def seed(corpus_root):
    corpus.write_words("sblgnt", "1Pet", [
        Word(2, 21, 1, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 18, 1, "ὅτι", "ὅτι", "G3754", "C-/--------"),          # conjunction: excluded
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
        Word(3, 18, 3, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 19, 1, "ἐστίν", "εἰμί", "G1510", "V-/3PAI-S--"),        # stoplist: excluded
        Word(3, 19, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),  # dup lemma: excluded
    ])
    corpus.write_verses("cuvs", "1Pet", [Verse(3, 18, "因基督也曾一次为罪受苦"), Verse(3, 19, "他借这灵曾去传道")])
    sdir = corpus.corpus_dir() / "strongs"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "greek.json").write_text(json.dumps({"G3958": {"lemma": "πάσχω", "strongs_def": "to suffer"}}), encoding="utf-8")
    (sdir / "hebrew.json").write_text("{}", encoding="utf-8")
    (sdir / "greek-lemma-map.json").write_text("{}", encoding="utf-8")

def test_pick_words(corpus_root):
    seed(corpus_root)
    picked = scaffold.pick_words(parse_ref("1Pet 3:18-19"))
    assert [w.lemma for w in picked] == ["Χριστός", "πάσχω"]

def test_build_structure(corpus_root, monkeypatch):
    seed(corpus_root)
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    monkeypatch.delenv("API_BIBLE_KEY", raising=False)
    md = scaffold.build(parse_ref("1Pet 3:18-19"), today="2026-07-19")
    assert md.startswith("# 1 Peter 3:18–19 · 彼得前书 3:18–19\n")
    assert "> scaffolded 2026-07-19 · " in md
    for h in ("## Text · 经文对照", "## Word Studies · 字词研究", "## Structure & Context · 结构与背景",
              "## Interpretation · 释经结论", "## Theology & Application · 神学综合与应用"):
        assert h in md
    assert "### πάσχω (ἔπαθεν, v. 18) — G3958 · aorist active indicative 3sg" in md
    assert "gloss: to suffer · in 1 Peter: 2× (2:21, 3:18)" in md
    assert "（your analysis · 你的分析）" in md
    assert "- **和合本** 因基督也曾一次为罪受苦" in md
    assert "> ESV unavailable" in md
    assert "Cross-references · 串珠：" in md

def test_write_and_force(corpus_root):
    seed(corpus_root)
    ref = parse_ref("1Pet 3:18-19")
    path = scaffold.write(ref)
    assert path == corpus.root() / "studies" / "1pet_3.18-19.md"
    assert path.exists()
    with pytest.raises(SystemExit):
        scaffold.write(ref)
    scaffold.write(ref, force=True)

def test_cli(corpus_root, capsys):
    seed(corpus_root)
    from exeg.cli import main
    assert main(["scaffold", "彼前3:18-19"]) == 0
    assert "studies/1pet_3.18-19.md" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_scaffold.py -q
```

Expected: FAIL — `ModuleNotFoundError: exeg.scaffold`.

- [ ] **Step 3: Implement**

`src/exeg/scaffold.py`:

```python
"""Generate a bilingual study file for a passage (exeg scaffold)."""
import datetime
import re
from pathlib import Path

from exeg import corpus, display, search
from exeg.corpus import Word
from exeg.refs import Ref

GREEK_STOP = {"εἰμί", "λέγω", "ἔχω", "γίνομαι"}
HEBREW_STOP = {"H1961", "H559", "H6213"}
SBLGNT_NOTICE = "SBLGNT: © 2010 Society of Biblical Literature and Logos Bible Software."
MAX_WORDS = 10
MAX_REFS = 12


def _pos(word: Word, greek: bool) -> str:
    if greek:
        return word.morph[:1]
    lemseg = word.lemma.split("/")
    morph = word.morph[1:] if word.morph[:1] in ("H", "A") else word.morph
    morphseg = morph.split("/")
    i = next((k for k, s in enumerate(lemseg) if re.search(r"\d", s)), len(lemseg) - 1)
    seg = morphseg[i] if i < len(morphseg) else morphseg[-1]
    return seg[:1]


def pick_words(ref: Ref) -> list[Word]:
    version = "sblgnt" if ref.book.nt else "wlc"
    picked, seen = [], set()
    for w in corpus.get_words(ref, version):
        if _pos(w, ref.book.nt) not in ("V", "N", "A"):
            continue
        if ref.book.nt and w.lemma in GREEK_STOP:
            continue
        if not ref.book.nt and w.strongs in HEBREW_STOP:
            continue
        if w.lemma in seen:
            continue
        seen.add(w.lemma)
        picked.append(w)
        if len(picked) >= MAX_WORDS:
            break
    return picked


def _word_section(ref: Ref) -> list[str]:
    greek, hebrew, _ = search._strongs_dicts()
    version = "sblgnt" if ref.book.nt else "wlc"
    lines: list[str] = []
    for w in pick_words(ref):
        occ = [x for x in corpus.read_words(version, ref.book.osis)
               if x.lemma == w.lemma]
        refs_s = ", ".join(f"{o.chapter}:{o.verse}" for o in
                           sorted({(o.chapter, o.verse): o for o in occ}.values(),
                                  key=lambda o: (o.chapter, o.verse))[:MAX_REFS])
        uniq = len({(o.chapter, o.verse) for o in occ})
        if uniq > MAX_REFS:
            refs_s += ", …"
        entry = (greek.get(w.strongs) or hebrew.get(w.strongs) or {})
        gloss = entry.get("strongs_def", "") or entry.get("kjv_def", "") or "—"
        surface = w.surface.replace("/", "")
        lines.append(f"### {w.lemma} ({surface}, v. {w.verse}) — {w.strongs or '?'} · "
                     f"{search.greek_morph_label(w.morph)}")
        lines.append(f"gloss: {gloss} · in {ref.book.en}: {uniq}× ({refs_s})")
        lines.append("（your analysis · 你的分析）")
        lines.append("")
    if not lines:
        lines = ["（no original-language text in corpus — run `exeg fetch`）", ""]
    return lines


def build(ref: Ref, versions: list[str] | None = None, today: str | None = None) -> str:
    versions = versions or display.default_versions(ref.book)
    texts, notes = display.gather(ref, versions)
    today = today or datetime.date.today().isoformat()
    labels = " | ".join(display.LABELS.get(v, v.upper()) for v in versions)
    out = [f"# {ref.en_label()} · {ref.zh_label(full=True)}",
           f"> scaffolded {today} · {labels}", "",
           "## Text · 经文对照", ""]
    out += [f"> {n}" for n in notes]
    ids = sorted({vid for tv in texts.values() for vid in tv})
    for ch, v in ids:
        out.append(f"### {ref.book.en} {ch}:{v} · {ref.book.zh_abbr} {ch}:{v}")
        for version in versions:
            if version not in texts:
                continue
            label = display.LABELS.get(version, version.upper())
            t = texts[version].get((ch, v))
            out.append(f"- **{label}** {t if t else f'[not in {label}]'}")
        out.append("")
    out += ["## Word Studies · 字词研究", ""]
    out += _word_section(ref)
    out += ["## Structure & Context · 结构与背景",
            "- Literary structure · 文学结构：",
            "- Historical setting · 历史背景：",
            "- Place in the book's argument · 在全书论证中的位置：", "",
            "## Interpretation · 释经结论", "", "",
            "## Theology & Application · 神学综合与应用",
            "- Cross-references · 串珠：", "", "---"]
    if "esv" in texts and texts["esv"]:
        from exeg import esv
        out.append(esv.NOTICE)
    if "nasb95" in texts and texts["nasb95"] and not corpus.has_version("nasb95"):
        from exeg import apibible
        out.append(apibible.NOTICE)
    if ("sblgnt" in texts and texts["sblgnt"]):
        out.append(SBLGNT_NOTICE)
    return "\n".join(out).rstrip() + "\n"


def write(ref: Ref, force: bool = False, versions: list[str] | None = None) -> Path:
    path = corpus.root() / "studies" / f"{ref.slug()}.md"
    if path.exists() and not force:
        raise SystemExit(f"{path} exists — use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(ref, versions), encoding="utf-8")
    return path


def cmd_scaffold(args) -> int:
    import sys
    from exeg import canon, refs
    try:
        ref = refs.parse_ref(args.ref)
    except (refs.BadRef, canon.UnknownBook) as e:
        print(str(e), file=sys.stderr)
        return 1
    versions = args.versions.split(",") if args.versions else None
    path = write(ref, force=args.force, versions=versions)
    print(f"wrote {path.relative_to(corpus.root())}")
    return 0
```

- [ ] **Step 4: Register the subcommand**

In `src/exeg/cli.py` `build_parser`, after the `word` block add:

```python
    from exeg import scaffold as _scaffold
    sc = sub.add_parser("scaffold", help="generate a bilingual study file")
    sc.add_argument("ref")
    sc.add_argument("--versions", help="comma list (default: originals,esv,nasb95,cuvs)")
    sc.add_argument("--force", action="store_true", help="overwrite an existing study file")
    sc.set_defaults(func=_scaffold.cmd_scaffold)
```

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/exeg/scaffold.py src/exeg/cli.py tests/test_scaffold.py
git commit -m "feat: exeg scaffold — bilingual study files"
```

---

### Task 13: AGENTS.md, CLAUDE.md, README, end-to-end smoke

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md`, `README.md`

**Interfaces:**
- Consumes: the finished CLI.
- Produces: the cross-agent contract all four agents (Claude Code, Codex, OpenCode, Hermes) read.

- [ ] **Step 1: Write AGENTS.md**

```markdown
# Exegesis Workspace — Agent Instructions

This project is a terminal Bible-exegesis workspace. You (the assisting agent)
help the user study passages. These rules bind every agent working here.

## Ground rules — non-negotiable

1. **Never quote Scripture from your own memory.** Every quotation must come
   from this repo's tools or corpus files:
   - `.venv/bin/exeg passage "1Pet 3:18-22"` (also accepts `彼前3:18-22`)
   - `.venv/bin/exeg word G3958` / `exeg word πάσχω`
   - `.venv/bin/exeg search "living hope" --versions web`
   - raw TSVs under `data/corpus/{version}/{Book}.tsv`
     (`chapter⇥verse⇥text`; Greek/Hebrew: `chapter⇥verse⇥idx⇥surface⇥lemma⇥strongs⇥morph`)
2. **Cite a verse reference for every textual claim.** No uncited assertions
   about what the text says.
3. **The `## Interpretation · 释经结论` section belongs to the user.** Draft
   there only when explicitly asked in the current conversation. You may draft
   in Word Studies and Structure & Context when asked.
4. **Bilingual convention:** mirror the file's EN/中文 heading style; keep
   Chinese in 简体 unless the user writes 繁體.
5. **Copyright:** ESV/NASB95 text comes only from `exeg passage` (licensed
   APIs/caches or the user's imported copy). Never paste ESV/NASB text from
   memory or the web; keep the attribution footer intact in study files.

## Workflow

- New passage: `.venv/bin/exeg scaffold "1Pet 3:18-22"` → edit
  `studies/1pet_3.18-22.md`. Refuses to overwrite without `--force`.
- Corpus missing? `.venv/bin/exeg fetch` (needs network; idempotent).
- API keys live in `.env` (gitignored): `ESV_API_KEY`, `API_BIBLE_KEY`.
- Run tests with `.venv/bin/pytest -q` before committing code changes.
- Commit study files; never commit anything under `data/`.

## Layout

- `src/exeg/` CLI source · `tests/` pytest suite
- `data/corpus/` normalized texts (gitignored, rebuildable via `exeg fetch`)
- `studies/` the user's study files (tracked — this is the real work product)
- `docs/superpowers/` design spec and implementation plan
```

- [ ] **Step 2: Write CLAUDE.md and README.md**

`CLAUDE.md`:

```markdown
Read and follow AGENTS.md. It is the single source of agent instructions for this repo.
```

`README.md`:

```markdown
# exegesis

Terminal Bible-exegesis workspace: a local multilingual corpus (SBLGNT, WLC,
WEB, KJV, 和合本, Strong's) + `exeg`, a CLI that prints parallel passages,
does word studies, and scaffolds bilingual (EN/中文) study files. ESV and
NASB95 display via licensed APIs (`ESV_API_KEY`, `API_BIBLE_KEY` in `.env`)
or `exeg import` of your own licensed copy.

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -e '.[dev]'
    .venv/bin/exeg fetch

## Use

    .venv/bin/exeg passage "1Pet 3:18-22"      # or 彼前3:18-22
    .venv/bin/exeg word G3958
    .venv/bin/exeg search "living hope"
    .venv/bin/exeg scaffold "1Pet 3:18-22"     # → studies/1pet_3.18-22.md

See AGENTS.md for the rules assisting agents must follow.
```

- [ ] **Step 3: End-to-end smoke test (real corpus, network)**

```bash
.venv/bin/pytest -q                                   # full suite green
.venv/bin/exeg fetch                                  # idempotent; "corpus healthy"
.venv/bin/exeg passage "彼前3:18-22" --versions sblgnt,web,cuvs
.venv/bin/exeg word G3958
.venv/bin/exeg search "living hope" --versions web --book 1Pet
.venv/bin/exeg scaffold "1Pet 3:18-22" --versions sblgnt,web,cuvs
head -40 studies/1pet_3.18-22.md
```

Expected: passage shows Greek + English + 中文 for vv. 18–22; `word G3958` reports πάσχω with 1 Peter occurrences; scaffold writes `studies/1pet_3.18-22.md` with all five spec headings. If the user has set `ESV_API_KEY`, rerun scaffold with default versions and confirm ESV lines + attribution footer.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md README.md studies
git commit -m "docs: AGENTS.md contract, README, CLAUDE.md pointer"
```

---

## Self-Review (completed during plan writing)

- **Spec coverage:** local corpus texts (T6), ESV/NASB via licensed channels + import (T8–T10), parallel passage (T7), word studies with pre-extracted lemma/Strong's/morph/gloss (T11–T12), structure/interpretation/application sections (T12), bilingual headings (T12), EN/中文 refs (T3), agent-agnostic contract (T13), error handling: unknown-ref suggestions (T2/T7), missing-corpus messages (T6/T7/T12), `[not in X]` markers (T7), no-overwrite (T12), API-degradation notes (T7–T9). Integrity checks (T6). Golden-ish scaffold test (T12).
- **Deviation:** `corpus.sqlite` dropped (flagged in header — corpus is small enough for linear scans).
- **Type consistency:** `Ref`/`Book`/`Verse`/`Word` signatures fixed in T2–T4 and used unchanged after; `gather()` returns `(texts, notes)` in both T7 and T12; both API clients expose `get_passage(ref) -> dict[(ch,v), str]` and `NOTICE`.
```
