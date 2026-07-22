"""Import a user-licensed translation into the local corpus (exeg import).

The imported text stays inside data/ (gitignored) and is never redistributed.
"""
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
    declared_version = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            # comment / directive; "# version: NAME" declares the version name
            m = line.strip().lower()
            if m.startswith("# version:"):
                declared_version = line.split(":", 1)[1].strip()
            continue
        if "\t" not in line:
            raise SystemExit(f"{path.name}:{lineno}: expected 'REF<TAB>text' "
                             f"(use a literal tab; see `exeg import --example`)")
        ref_s, text = line.split("\t", 1)
        try:
            ref = refs.parse_ref(ref_s.strip())
        except (refs.BadRef, canon.UnknownBook) as e:
            raise SystemExit(f"{path.name}:{lineno}: {e}") from e
        if ref.verse is None or (ref.chapter, ref.verse) != (ref.end_chapter, ref.end_verse):
            raise SystemExit(f"{path.name}:{lineno}: one single-verse reference per line, got {ref_s!r}")
        books.setdefault(ref.book.osis, []).append(corpus.Verse(ref.chapter, ref.verse, text.strip()))
    if declared_version and not version:
        version = declared_version
    if not version:
        raise SystemExit("no version given (use --version NAME or a '# version: NAME' header)")
    for osis, verses in books.items():
        verses.sort(key=lambda v: (v.chapter, v.verse))
        corpus.write_verses(version, osis, verses)
        log(f"{version}/{osis}: {len(verses)} verses")
    return len(books)


def import_path(path: Path, version: str | None, fmt: str | None = None, log=print) -> int:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"not found: {path}")
    if fmt is None:
        fmt = "usfm" if path.is_dir() or path.suffix.lower() in (".usfm", ".sfm") else "tsv"
    if fmt == "usfm":
        if not version:
            raise SystemExit("USFM import needs --version NAME")
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        files = [f for f in files if f.suffix.lower() in (".usfm", ".sfm")]
        if not files:
            raise SystemExit(f"no .usfm/.sfm files under {path}")
        n = _import_usfm_files(files, version, log)
    else:
        n = _import_tsv(path, version or "", log)
    if n == 0:
        raise SystemExit("nothing imported")
    log(f"imported {n} book(s) into data/corpus/{version or ''}/ "
        "(local only, gitignored — your licensed copy is never redistributed)")
    return n


EXAMPLE = """\
# exeg translation import — TSV format
# - one verse per line:  REFERENCE<TAB>verse text
# - REFERENCE is a single verse: 'Gen 1:1', '1Pet 3:18', 'Ps 23:1' (also 中文 like 彼前3:18)
# - lines starting with # are comments; '# version: NAME' sets the corpus version name
# - a literal TAB separates the reference from the text (not spaces)
# - verses may be in any order; partial books are fine
# - the imported text stays local (data/corpus/<NAME>/, gitignored) and is never shared
#
# Example (save as mytranslation.tsv):

# version: mytranslation
Gen 1:1	In the beginning God created the heavens and the earth.
Gen 1:2	And the earth was without form, and void; and darkness was on the face of the deep.
Ps 23:1	The LORD is my shepherd; I shall not want.
1Pet 3:18	For Christ also suffered once for sins, the righteous for the unrighteous...
彼前3:18	因基督也曾一次为罪受苦，就是义的代替不义的...

# Then run:
#   exeg import mytranslation.tsv
# (or: exeg import mytranslation.tsv --version mytranslation)
# and in the TUI:  :versions mytranslation,cuvs   or pick it on the settings page.
"""


def cmd_import(args) -> int:
    if getattr(args, "example", False):
        print(EXAMPLE)
        return 0
    import_path(Path(args.path), getattr(args, "version", None), args.format)
    return 0
