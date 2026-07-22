"""Hierarchical note store as a greppable markdown tree under notes/.

    notes/<Osis>/_book.md            book note
    notes/<Osis>/<ch>/_chapter.md    chapter note
    notes/<Osis>/<ch>/<v>.md          verse note
    notes/<Osis>/<ch>/<v>.<idx>.md    word-occurrence note
    notes/lexicon/<Strong>.md         cross-verse lexicon note

Every node "exists" (corpus + canon define them); notes are optional
attachments — no empty files are written. Notes are plain markdown so any
agent can read/edit them under the AGENTS.md scripture-citation rules.
"""
from __future__ import annotations

from pathlib import Path

from exeg import corpus


def notes_root() -> Path:
    return corpus.root() / "notes"


def _book_dir(osis: str) -> Path:
    return notes_root() / osis


def _chapter_dir(osis: str, ch: int) -> Path:
    return _book_dir(osis) / str(ch)


def book_path(osis: str) -> Path:
    return _book_dir(osis) / "_book.md"


def chapter_path(osis: str, ch: int) -> Path:
    return _chapter_dir(osis, ch) / "_chapter.md"


def verse_path(osis: str, ch: int, v: int) -> Path:
    return _chapter_dir(osis, ch) / f"{v}.md"


def word_path(osis: str, ch: int, v: int, idx: int) -> Path:
    return _chapter_dir(osis, ch) / f"{v}.{idx}.md"


def lexicon_path(strongs: str) -> Path:
    return notes_root() / "lexicon" / f"{strongs}.md"


def has_book_note(osis: str) -> bool:
    return book_path(osis).exists()


def has_chapter_note(osis: str, ch: int) -> bool:
    return chapter_path(osis, ch).exists()


def has_verse_note(osis: str, ch: int, v: int) -> bool:
    return verse_path(osis, ch, v).exists()


def has_word_note(osis: str, ch: int, v: int, idx: int) -> bool:
    return word_path(osis, ch, v, idx).exists()


def read_note(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_book(osis: str) -> str:
    return read_note(book_path(osis))


def read_chapter(osis: str, ch: int) -> str:
    return read_note(chapter_path(osis, ch))


def read_verse(osis: str, ch: int, v: int) -> str:
    return read_note(verse_path(osis, ch, v))


def read_word(osis: str, ch: int, v: int, idx: int) -> str:
    return read_note(word_path(osis, ch, v, idx))


def read_lexicon(strongs: str) -> str:
    return read_note(lexicon_path(strongs))


def write_note(path: Path, text: str) -> None:
    """Write a note, deleting the file if the text is blank."""
    text = text.rstrip()
    if not text:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def write_book(osis: str, text: str) -> None:
    write_note(book_path(osis), text)


def write_chapter(osis: str, ch: int, text: str) -> None:
    write_note(chapter_path(osis, ch), text)


def write_verse(osis: str, ch: int, v: int, text: str) -> None:
    write_note(verse_path(osis, ch, v), text)


def write_word(osis: str, ch: int, v: int, idx: int, text: str) -> None:
    write_note(word_path(osis, ch, v, idx), text)


def write_lexicon(strongs: str, text: str) -> None:
    write_note(lexicon_path(strongs), text)


def list_verse_word_notes(osis: str, ch: int, v: int) -> list[int]:
    """Word indices that have a note attached for this verse."""
    d = _chapter_dir(osis, ch)
    if not d.is_dir():
        return []
    out = []
    prefix = f"{v}."
    for p in d.glob(f"{prefix}*.md"):
        try:
            out.append(int(p.stem[len(prefix):]))
        except ValueError:
            continue
    return sorted(out)


# ---- meta / settings --------------------------------------------------------


def meta_path() -> Path:
    return notes_root() / "_meta.json"


def read_meta() -> dict:
    import json
    p = meta_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_meta(data: dict) -> None:
    import json
    p = meta_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- export (compile notes + corpus into a study file) ----------------------


def export_ref(ref, versions) -> str:
    """Build a bilingual study-file string for `ref` interleaving any attached
    notes (book/chapter/verse/word). Reuses display.gather for the texts."""
    import datetime
    from exeg import display, corpus
    texts, notes_msgs = display.gather(ref, versions)
    today = datetime.date.today().isoformat()
    labels = " | ".join(display.LABELS.get(v, v.upper()) for v in versions)
    out = [f"# {ref.en_label()} · {ref.zh_label(full=True)}",
           f"> exported {today} · {labels}", "", "## Text · 经文对照", ""]
    out += [f"> {n}" for n in notes_msgs]
    ids = sorted({vid for tv in texts.values() for vid in tv})
    osis = ref.book.osis
    for ch, v in ids:
        out.append(f"### {ref.book.en} {ch}:{v} · {ref.book.zh_abbr} {ch}:{v}")
        for version in versions:
            if version not in texts:
                continue
            label = display.LABELS.get(version, version.upper())
            t = texts[version].get((ch, v))
            out.append(f"- **{label}** {t if t else f'[not in {label}]'}")
        vn = read_verse(osis, ch, v)
        if vn:
            out += ["", f"  > note · v.{v}", vn.rstrip(), ""]
        # word-level notes for this verse
        for idx in list_verse_word_notes(osis, ch, v):
            wn = read_word(osis, ch, v, idx)
            if wn:
                out += [f"  > word note · v.{v} #{idx}", wn.rstrip(), ""]
    bn = read_book(osis)
    cn = read_chapter(osis, ref.chapter) if ref.chapter == ref.end_chapter else ""
    out += ["## Notes · 笔记", ""]
    if bn:
        out += [f"### {ref.book.en} (book)", bn.rstrip(), ""]
    if cn:
        out += [f"### {ref.book.en} {ref.chapter} (chapter)", cn.rstrip(), ""]
    if not (bn or cn or any(read_verse(osis, c, v) for c, v in ids)):
        out.append("（no notes attached yet）")
    out.append("")
    return "\n".join(out).rstrip() + "\n"