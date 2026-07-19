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
