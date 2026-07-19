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
