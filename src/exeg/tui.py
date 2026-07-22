"""exeg TUI — a focus-driven curses Bible-exegesis workspace.

Phases 1–4: nav + content modes, Books/Chapters/Verses/Words columns, three
view scopes, focus highlight, no-color fallback, word study + result views,
note persistence (markdown tree) with a modal insert editor (and a readline
popup fallback), pin, search-within-preview, history, settings.
See docs/superpowers/specs/2026-07-19-tui-design.md.

Pure logic lives in `Controller` (no curses) so it is unit-testable; `run()`
is the curses driver.
"""
import curses
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field

from exeg import canon, corpus, display, notes, refs, search
from exeg.i18n import tr

ORIG = {"nt": "sblgnt", "ot": "wlc"}
LOCAL_DEFAULT = ["cuvs", "asv"]
SEARCH_DEFAULT = ["web", "kjv", "cuvs"]

SCOPES = ("window", "chapter", "verse")
DEFAULT_BOOK = "1Pet"
DEFAULT_CHAPTER = 3
DEFAULT_VERSE = 18
DEFAULT_WINDOW = 5


KIND_HEADER = "header"
KIND_FOCUS = "focus"
KIND_DIM = "dim"
KIND_NORMAL = "normal"
KIND_NOTE = "note"
KIND_TITLE = "title"
KIND_STATUS = "status"
KIND_COLHDR = "colhdr"
KIND_SEL = "sel"
KIND_ITEM = "item"
KIND_MSG = "msg"
KIND_TOKEN = "token"
KIND_OCCUR = "occur"
KIND_OCCUR_SEL = "occur_sel"
KIND_LABEL = "label"


@dataclass
class Node:
    book_idx: int
    chapter: int
    verse: int

    def book(self) -> canon.Book:
        return canon.BOOKS[self.book_idx]

    def __eq__(self, other):
        return (isinstance(other, Node) and self.book_idx == other.book_idx
                and self.chapter == other.chapter and self.verse == other.verse)

    def __hash__(self):
        return hash((self.book_idx, self.chapter, self.verse))


def _local_default(book: canon.Book) -> list[str]:
    return [ORIG["nt" if book.nt else "ot"]] + list(LOCAL_DEFAULT)


def _max_verse(book: canon.Book, chapter: int) -> int:
    osis = book.osis
    for v in ("cuvs", "web", "kjv", ORIG["nt" if book.nt else "ot"]):
        verses = corpus.read_verses(v, osis)
        hi = max((vv.verse for vv in verses if vv.chapter == chapter), default=0)
        if hi:
            return hi
    return 0


def _gather(ref: refs.Ref, versions: list[str]):
    try:
        return display.gather(ref, versions)
    except Exception as e:
        return {}, [f"error: {e}"]


def _osis_index(osis: str) -> int:
    return next(i for i, b in enumerate(canon.BOOKS) if b.osis == osis)


def _surface(w: corpus.Word) -> str:
    return w.surface.replace("/", "")


def _word_versions() -> list[str]:
    return ["sblgnt", "wlc"]


def _key_set(env_var: str) -> bool:
    import os
    from exeg import setup
    return setup.key_is_set(env_var)


# --------------------------------------------------------------------------- #
# Controller (pure logic, no curses)
# --------------------------------------------------------------------------- #

class Controller:
    def __init__(self, versions: list[str] | None = None, intro: bool = False):
        bi = canon.find_book(DEFAULT_BOOK).osis
        self.book_idx = next(i for i, b in enumerate(canon.BOOKS) if b.osis == bi)
        self.chapter = DEFAULT_CHAPTER
        self.verse = DEFAULT_VERSE
        self.focus = Node(self.book_idx, self.chapter, self.verse)
        self.sel = Node(self.book_idx, self.chapter, self.verse)
        self.sel_word = 1                       # navigator's word selection
        self.nav_visible = True
        self.nav_col = 0                        # 0 books, 1 chapters, 2 verses, 3 words
        self.scope = "window"
        self.window = DEFAULT_WINDOW
        # versions: user override vs testament-aware auto originals
        self._versions_custom = versions is not None
        self.versions = versions or _local_default(self.focus.book())
        self.translations: list[str] = ["cuvs", "asv"]   # refined below from meta
        self.study_set: refs.Ref | None = None
        self.message = ""
        self.running = True
        self.intro = intro

        # view: "verse" | "word" | "result"
        self.view = "verse"
        self.word_idx: int | None = None        # focused word occurrence
        self.word_result: dict = {}
        self.word_cursor: int = 0
        self.result_lines: list[tuple[str, str]] = []
        self.result_items: list[tuple[int, int, int]] = []
        self.result_cursor: int = 0
        self.result_title: str = ""

        # notes / editor
        self.editing = False
        self.note_lines: list[str] = []
        self.note_cy: int = 0
        self.note_cx: int = 0
        self.note_target: tuple = ()
        self.note_dirty = False
        self.editor_mode = "inline"             # "inline" | "popup"
        self.show_help = False                   # `?` overlay
        self.help_scroll = 0
        self.settings_cursor = 0
        self.intro_cursor = 0
        self._pending_apikey: tuple | None = None   # (env_var, label) for driver
        self._pending_setup = False                 # driver runs the full wizard
        self._pending_restore = False                # driver asks confirm, then restore
        self._pending_optional_fetch = False         # driver downloads public study data

        # bookmark (set with p, return with b) — a single saved location
        self.bookmark: tuple | None = None    # (Node, view, word_idx)

        # search-within-preview
        self.find_pat: str = ""
        self.find_hits: list[int] = []
        self.find_idx: int = -1
        self.find_target_line: int | None = None

        # settings
        self.highlight = "auto"
        m = notes.read_meta()
        self.lang = m.get("lang", "en")
        if self.lang not in ("en", "zh"):
            self.lang = "en"
        if isinstance(m.get("window"), int):
            self.window = max(1, min(40, m["window"]))
        if m.get("highlight") in ("color", "minimal", "auto"):
            self.highlight = m["highlight"]
        if m.get("editor") in ("inline", "popup"):
            self.editor_mode = m["editor"]
        if isinstance(m.get("translations"), list) and m["translations"]:
            self.translations = list(m["translations"])
        self.show_verse_marks = bool(m.get("show_verse_marks", True))
        self.notemark = m.get("notemark", "✎") or "✎"

    # ---- versions (testament-aware) ----------------------------------------

    def effective_versions(self) -> list[str]:
        if self._versions_custom:
            return self.versions
        original = ORIG["nt" if self.shown().book().nt else "ot"]
        return ([original] if corpus.has_version(original) else []) + list(self.translations)

    # ---- display state (pin-aware) -----------------------------------------

    def shown(self) -> Node:
        if self.nav_visible and not self.editing:
            return self.sel
        return self.focus

    # ---- refs --------------------------------------------------------------

    def study_ref(self) -> refs.Ref:
        if self.study_set is not None:
            return self.study_set
        b = self.focus.book()
        hi = _max_verse(b, self.focus.chapter) or 1
        return refs.Ref(b, self.focus.chapter, 1, self.focus.chapter, hi)

    def verse_list(self) -> list[tuple[int, int]]:
        ref = self.study_ref()
        ids: set[tuple[int, int]] = set()
        for v in self.effective_versions():
            if v in ("esv", "nasb95") and not corpus.has_book(v, ref.book.osis):
                continue
            for vv in corpus.get_verses(v, ref):
                ids.add((vv.chapter, vv.verse))
        if not ids:
            b = ref.book
            for ch in range(ref.chapter, ref.end_chapter + 1):
                hi = _max_verse(b, ch)
                for vv in range(1, hi + 1):
                    ids.add((ch, vv))
        return sorted(ids)

    def view_ref(self) -> refs.Ref:
        n = self.shown()
        b = n.book()
        if self.scope == "verse":
            return refs.Ref(b, n.chapter, n.verse, n.chapter, n.verse)
        if self.scope == "window":
            hi = _max_verse(b, n.chapter) or 1
            lo = max(1, n.verse - self.window)
            end = min(hi, n.verse + self.window)
            return refs.Ref(b, n.chapter, lo, n.chapter, end)
        hi = _max_verse(b, n.chapter) or 1
        return refs.Ref(b, n.chapter, 1, n.chapter, hi)

    # ---- focus changes ----------------------------------------------------

    def _set_focus_state(self, node: Node, view="verse", word_idx=None):
        self.focus = node
        self.sel = Node(node.book_idx, node.chapter, node.verse)
        self.book_idx = node.book_idx
        self.chapter = node.chapter
        self.verse = node.verse
        self.view = view
        self.word_idx = word_idx

    def goto(self, node: Node, view="verse", word_idx=None):
        """Change focus (no history — `b` returns to the bookmark, set with `p`)."""
        self._set_focus_state(node, view, word_idx)

    def set_bookmark(self):
        """Record/replace the bookmark at the current position."""
        self.bookmark = (self.focus, self.view, self.word_idx)
        self.message = tr(self.lang, "bookmarked", ref=f"{self.focus.book().en} {self.focus.chapter}:{self.focus.verse}")

    def back(self):
        """Return to the bookmark (if any)."""
        if self.bookmark is None:
            self.message = tr(self.lang, "no_bookmark")
            return
        node, view, word = self.bookmark
        self._set_focus_state(node, view, word)
        self.nav_visible = False
        self.message = tr(self.lang, "returned", ref=f"{node.book().en} {node.chapter}:{node.verse}")

    # ---- settings page -----------------------------------------------------

    def open_settings(self):
        self.view = "settings"
        self.nav_visible = False
        self.settings_cursor = 0
        idxs = self._selectable_settings_indexes()
        if idxs:
            self.settings_cursor = idxs[0]
        self.message = ""

    def close_settings(self):
        self.view = "verse"
        self.message = ""

    # ---- first-run intro (curses, Demo C) ------------------------------------

    def open_intro(self):
        self.intro = True
        self.intro_cursor = 0
        idxs = self._selectable_intro_indexes()
        if idxs:
            self.intro_cursor = idxs[0]

    def _download_item(self):
        from exeg import fetch
        status = fetch.optional_pack_status()
        status_label = tr(self.lang, "pack_status_" + status)
        return {"type": "download", "key": "download_pack",
                "label": f"{tr(self.lang, 'download_pack')} ({status_label})"}

    def intro_items(self):
        note = ("ESV / NASB95 / LSB are not included by default: they require a free "
                "API key, are licensed for non-commercial use, and fetch each verse "
                "online (slow). ESV & NASB95 can be added later in Settings with your "
                "own key; LSB is not available offline.")
        return [
            {"type": "section", "label": tr(self.lang, "set_iface_lang")},
            {"type": "radio", "key": "lang", "value": "en", "label": "English", "active": self.lang == "en"},
            {"type": "radio", "key": "lang", "value": "zh", "label": "中文", "active": self.lang == "zh"},
            {"type": "section", "label": tr(self.lang, "set_translations")},
            {"type": "note", "label": tr(self.lang, "set_orig_auto")},
            {"type": "section", "label": tr(self.lang, "set_section_zh")},
            {"type": "bool", "key": "ver", "value": "cuvs", "label": "和合本 CUVS", "active": "cuvs" in self.translations},
            {"type": "section", "label": tr(self.lang, "set_section_en")},
            {"type": "bool", "key": "ver", "value": "web", "label": "WEB", "active": "web" in self.translations},
            {"type": "bool", "key": "ver", "value": "kjv", "label": "KJV", "active": "kjv" in self.translations},
            {"type": "bool", "key": "ver", "value": "asv", "label": "ASV (1901, public domain)", "active": "asv" in self.translations},
            {"type": "section", "label": tr(self.lang, "set_section_la")},
            {"type": "bool", "key": "ver", "value": "vulgate", "label": "Vulgate", "active": "vulgate" in self.translations},
            {"type": "section", "label": "Not included by default / 默认未包含"},
            {"type": "note", "label": note},
            {"type": "section", "label": tr(self.lang, "study_data")},
            self._download_item(),
            {"type": "action", "key": "begin", "label": "Begin  — start the workspace"},
        ]

    def _selectable_intro_indexes(self):
        return [i for i, it in enumerate(self.intro_items())
                if it["type"] in ("radio", "bool", "download", "action")]

    def move_intro_cursor(self, delta):
        idxs = self._selectable_intro_indexes()
        if not idxs:
            return
        try:
            pos = idxs.index(self.intro_cursor)
        except ValueError:
            pos = 0
        self.intro_cursor = idxs[(pos + delta) % len(idxs)]

    def toggle_intro(self):
        items = self.intro_items()
        if self.intro_cursor >= len(items):
            return
        it = items[self.intro_cursor]
        if it["type"] == "radio" and it["key"] == "lang":
            self.lang = it["value"]
        elif it["type"] == "bool" and it["key"] == "ver":
            if it["value"] in self.translations:
                self.translations = [v for v in self.translations if v != it["value"]]
            else:
                self.translations.append(it["value"])
            self._versions_custom = False
        elif it["type"] == "download":
            self._pending_optional_fetch = True
        elif it["type"] == "action" and it["key"] == "begin":
            self.finish_intro()

    def finish_intro(self):
        self._persist_meta()
        m = notes.read_meta()
        m["setup_done"] = True
        notes.write_meta(m)
        self.intro = False
        self.message = ""

    def render_intro(self):
        title = "exeg — first-run setup  (j/k move · Enter select · choose Begin to start)"
        lines = [(title, KIND_HEADER), ("─" * 60, KIND_COLHDR), ("", KIND_NORMAL)]
        for i, it in enumerate(self.intro_items()):
            t = it["type"]
            if t == "section":
                lines.append(("", KIND_NORMAL))
                lines.append((it["label"], KIND_COLHDR))
                continue
            if t == "note":
                lines.append(("    " + it["label"], KIND_NOTE))
                continue
            if t == "radio":
                mark = "(●)" if it["active"] else "( )"
            elif t == "bool":
                mark = "[x]" if it["active"] else "[ ]"
            elif t == "download":
                mark = "↓"
            else:
                mark = ""
            sel = (i == self.intro_cursor)
            prefix = "  ▶ " if sel else "    "
            lines.append((f"{prefix}{mark} {it['label']}",
                          KIND_OCCUR_SEL if sel else KIND_OCCUR))
        return lines, 2

    def settings_items(self):
        from exeg import i18n
        items = [
            {"type": "section", "label": tr(self.lang, "set_iface_lang")},
            {"type": "radio", "key": "lang", "value": "en",
             "label": i18n.lang_name("en"), "active": self.lang == "en"},
            {"type": "radio", "key": "lang", "value": "zh",
             "label": i18n.lang_name("zh"), "active": self.lang == "zh"},
            {"type": "section", "label": tr(self.lang, "set_translations")},
            {"type": "note", "label": tr(self.lang, "set_orig_auto")},
            {"type": "section", "label": tr(self.lang, "set_section_zh")},
            {"type": "bool", "key": "ver", "value": "cuvs",
             "label": "和合本 CUVS", "active": "cuvs" in self.translations},
            {"type": "section", "label": tr(self.lang, "set_section_en")},
            {"type": "bool", "key": "ver", "value": "web",
             "label": "WEB", "active": "web" in self.translations},
            {"type": "bool", "key": "ver", "value": "kjv",
             "label": "KJV", "active": "kjv" in self.translations},
            {"type": "bool", "key": "ver", "value": "asv",
             "label": "ASV (1901, public domain)", "active": "asv" in self.translations},
            {"type": "bool", "key": "ver", "value": "esv",
             "label": "ESV (API key)", "active": "esv" in self.translations},
            {"type": "bool", "key": "ver", "value": "nasb95",
             "label": "NASB95 (API key)", "active": "nasb95" in self.translations},
            {"type": "section", "label": tr(self.lang, "set_section_la")},
            {"type": "bool", "key": "ver", "value": "vulgate",
             "label": "Vulgate", "active": "vulgate" in self.translations},
            {"type": "section", "label": tr(self.lang, "study_data")},
            self._download_item(),
            {"type": "section", "label": "API keys"},
            {"type": "apikey", "key": "apikey", "value": "ESV_API_KEY",
             "label": "ESV API key  - Enter to paste",
             "active": _key_set("ESV_API_KEY")},
            {"type": "apikey", "key": "apikey", "value": "API_BIBLE_KEY",
             "label": "NASB95 API key  - Enter to paste",
             "active": _key_set("API_BIBLE_KEY")},
            {"type": "section", "label": "Display"},
            {"type": "bool", "key": "show_verse_marks", "value": "on",
             "label": "Mark verses that have a note",
             "active": self.show_verse_marks},
            {"type": "section", "label": "Reset"},
            {"type": "restore", "key": "restore", "value": "restore",
             "label": "Restore all settings to defaults", "active": False},
        ]
        return items

    def _selectable_settings_indexes(self):
        return [i for i, it in enumerate(self.settings_items())
                if it["type"] in ("radio", "bool", "download", "apikey", "restore")]

    def move_settings_cursor(self, delta):
        idxs = self._selectable_settings_indexes()
        if not idxs:
            return
        try:
            pos = idxs.index(self.settings_cursor)
        except ValueError:
            pos = 0
        pos = (pos + delta) % len(idxs)
        self.settings_cursor = idxs[pos]

    def toggle_settings(self):
        items = self.settings_items()
        if self.settings_cursor >= len(items):
            return
        it = items[self.settings_cursor]
        if it["type"] == "radio" and it["key"] == "lang":
            self.lang = it["value"]
        elif it["type"] == "apikey":
            self._pending_apikey = (it["value"], it["label"])
        elif it["type"] == "restore":
            self._pending_restore = True
        elif it["type"] == "download":
            self._pending_optional_fetch = True
        elif it["type"] == "bool" and it["key"] == "show_verse_marks":
            self.show_verse_marks = not self.show_verse_marks
        elif it["type"] == "bool" and it["key"] == "ver":
            if it["value"] in self.translations:
                self.translations = [v for v in self.translations if v != it["value"]]
            else:
                self.translations.append(it["value"])
            self._versions_custom = False  # settings manages the translation set
        self._persist_meta()

    def render_settings(self):
        hint = tr(self.lang, "settings_title")
        lines = [(hint, KIND_HEADER),
                ("─" * 60, KIND_COLHDR), ("", KIND_NORMAL)]
        for i, it in enumerate(self.settings_items()):
            t = it["type"]
            if t == "section":
                lines.append(("", KIND_NORMAL))
                lines.append((it["label"], KIND_COLHDR))
                continue
            if t == "note":
                lines.append(("    " + it["label"], KIND_NOTE))
                continue
            if t == "radio":
                mark = "(●)" if it["active"] else "( )"
            elif t == "bool":
                mark = "[x]" if it["active"] else "[ ]"
            elif t == "download":
                mark = "↓"
            elif t == "apikey":
                mark = "[set]" if it["active"] else "[ -- ]"
            elif t == "restore":
                sel = (i == self.settings_cursor)
                prefix = "  ▶ " if sel else "    "
                lines.append((f"{prefix}↺ {it['label']}",
                              KIND_OCCUR_SEL if sel else KIND_OCCUR))
                continue
            else:
                mark = ""
            sel = (i == self.settings_cursor)
            prefix = "  ▶ " if sel else "    "
            lines.append((f"{prefix}{mark} {it['label']}",
                          KIND_OCCUR_SEL if sel else KIND_OCCUR))
        lines.append(("", KIND_NORMAL))
        lines.append(("j/k move · Enter toggle/paste · Esc back  ·  Ctrl-C skips a key paste",
                      KIND_NOTE))
        return lines, 2

    # ---- note target -------------------------------------------------------

    def focus_note_target(self) -> tuple:
        """`i` always attaches the note to the focused VERSE (so the verse mark
        shows). Word-occurrence notes are used in word view; chapter/book notes
        are not created via `i`."""
        n = self.focus
        if self.view == "word" and self.word_idx is not None:
            return ("word", n.book().osis, n.chapter, n.verse, self.word_idx)
        return ("verse", n.book().osis, n.chapter, n.verse)

    def _load_note(self, target: tuple) -> str:
        kind = target[0]
        if kind == "verse":
            return notes.read_verse(target[1], target[2], target[3])
        if kind == "word":
            return notes.read_word(target[1], target[2], target[3], target[4])
        if kind == "chapter":
            return notes.read_chapter(target[1], target[2])
        if kind == "book":
            return notes.read_book(target[1])
        return ""

    def _save_note(self, target: tuple, text: str) -> None:
        kind = target[0]
        if kind == "verse":
            notes.write_verse(target[1], target[2], target[3], text)
        elif kind == "word":
            notes.write_word(target[1], target[2], target[3], target[4], text)
        elif kind == "chapter":
            notes.write_chapter(target[1], target[2], text)
        elif kind == "book":
            notes.write_book(target[1], text)

    # ---- rendering ---------------------------------------------------------

    def render_content(self) -> tuple[list[tuple[str, str]], int]:
        if self.intro:
            return self.render_intro()
        if self.show_help:
            return self._render_help()
        if self.editing:
            # scripture stays on top; the editor is drawn as a bottom pane
            return self._render_verse()
        if self.view == "result":
            return list(self.result_lines), self._result_focus_line()
        if self.view == "settings":
            return self.render_settings()
        if self.view == "word":
            return self._render_word()
        return self._render_verse()

    def _result_focus_line(self) -> int:
        return 1 + self.result_cursor if self.result_items else -1

    def _render_verse(self) -> tuple[list[tuple[str, str]], int]:
        n = self.shown()
        ref = self.view_ref()
        vers = self.effective_versions()
        texts, gnotes = _gather(ref, vers)
        ids = sorted({vid for tv in texts.values() for vid in tv})
        lines: list[tuple[str, str]] = []
        for note in gnotes:
            lines.append((f"> {note}", KIND_MSG))
        if not ids:
            lines.append((f"> no local text for {ref.en_label()} — run `exeg fetch`", KIND_MSG))
            return lines, -1
        focus_key = (n.chapter, n.verse)
        focus_line = -1
        for (ch, v) in ids:
            is_focus = (ch, v) == focus_key
            if is_focus and focus_line == -1:
                focus_line = len(lines)
            note_mark = ""
            if self.show_verse_marks and notes.has_verse_note(ref.book.osis, ch, v):
                note_mark = (self.notemark + " ") if self.notemark else ""
            hdr = f"{note_mark}{ref.book.en} {ch}:{v} · {ref.book.zh_abbr} {ch}:{v}"
            lines.append((hdr, KIND_FOCUS if is_focus else
                          (KIND_DIM if self.scope == "window" else KIND_HEADER)))
            for version in vers:
                if version not in texts:
                    continue
                label = display.LABELS.get(version, version.upper())
                text = texts[version].get((ch, v))
                body = text if text else f"[not in {label}]"
                lines.append((_version_line(label, body), KIND_FOCUS if is_focus else
                              (KIND_DIM if self.scope == "window" else KIND_NORMAL)))
        if (self.scope == "verse" and focus_line != -1 and not self.nav_visible
                and not self.editing):
            ntext = notes.read_verse(ref.book.osis, n.chapter, n.verse)
            lines.append(("", KIND_NOTE))
            if ntext:
                lines.append((f"  {tr(self.lang, 'note_word')}({ref.book.zh_abbr} {n.chapter}:{n.verse}):", KIND_NOTE))
                for ln in ntext.rstrip("\n").splitlines():
                    lines.append((f"    {ln}", KIND_NOTE))
            else:
                lines.append((f"  {tr(self.lang, 'note_word')}({ref.book.zh_abbr} {n.chapter}:{n.verse}): {tr(self.lang, 'note_edit_prompt')}",
                              KIND_NOTE))
        return lines, focus_line

    def _render_word(self) -> tuple[list[tuple[str, str]], int]:
        n = self.focus
        widx = self.word_idx
        b = n.book()
        vref = refs.Ref(b, n.chapter, n.verse, n.chapter, n.verse)
        lines: list[tuple[str, str]] = []
        r = self.word_result
        lemma = r.get("lemma", "")
        strongs = r.get("strongs", "")
        gloss = r.get("gloss", "")
        lines.append((f"{b.en} {n.chapter}:{n.verse} · {tr(self.lang, 'word_study')} · {lemma} ({strongs or '?'})",
                      KIND_HEADER))
        if gloss:
            lines.append((f"  " + tr(self.lang, "gloss") + f": {gloss}", KIND_LABEL))
        words = corpus.get_words(vref, ORIG["nt" if b.nt else "ot"])
        toks = [f"[{_surface(w)}]" if w.idx == widx else _surface(w) for w in words]
        if toks:
            label = display.LABELS.get(ORIG["nt" if b.nt else "ot"], "ORIG")
            lines.append((_version_line(label, " ".join(toks)), KIND_TOKEN))
        vers = self.effective_versions()
        texts, gnotes = _gather(vref, vers)
        for note in gnotes:
            lines.append((f"> {note}", KIND_MSG))
        for version in vers:
            if version in _word_versions():
                continue
            if version not in texts:
                continue
            label = display.LABELS.get(version, version.upper())
            t = texts[version].get((n.chapter, n.verse))
            if t:
                lines.append((_version_line(label, t), KIND_NORMAL))
        by_book = r.get("by_book", {})
        if by_book:
            counts = ", ".join(f"{k}: {n}" for k, n in sorted(by_book.items())[:8])
            lines.append((f"  " + tr(self.lang, "in_corpus") + f": {counts}", KIND_LABEL))
        occ = r.get("occurrences", [])
        lines.append(("", KIND_NOTE))
        lines.append(("  " + tr(self.lang, "occurrences", n=len(occ)), KIND_LABEL))
        for i, (ver, osis, ch, v, surface, morph) in enumerate(occ):
            mark = "▶" if i == self.word_cursor else " "
            mlbl = search.greek_morph_label(morph)
            lines.append((f" {mark} {osis} {ch}:{v}  {surface}  ({mlbl})",
                          KIND_OCCUR_SEL if i == self.word_cursor else KIND_OCCUR))
        return lines, 2

    def editor_lines(self) -> list[tuple[str, str]]:
        """Lines for the bottom editor pane (header + note buffer)."""
        target = self.note_target
        kind = target[0] if target else "verse"
        n = self.focus
        hint = tr(self.lang, "esc_save_hint")
        if kind == "verse":
            head = f"{tr(self.lang, 'note_word')} · {n.book().en} {n.chapter}:{n.verse}  ({hint})"
        elif kind == "word":
            head = f"{tr(self.lang, 'note_word')} · {n.book().en} {n.chapter}:{n.verse} #{self.word_idx}  ({hint})"
        elif kind == "chapter":
            head = f"{tr(self.lang, 'note_word')} · {n.book().en} {n.chapter} ({tr(self.lang, 'note_chapter')})  ({hint})"
        else:
            head = f"{tr(self.lang, 'note_word')} · {n.book().en} ({tr(self.lang, 'note_book')})  ({hint})"
        out: list[tuple[str, str]] = [(head, KIND_HEADER), ("", KIND_NOTE)]
        for ln in self.note_lines:
            out.append((ln if ln else " ", KIND_NOTE))
        if not self.note_lines:
            out.append((" ", KIND_NOTE))
        return out

    def _render_help(self) -> tuple[list[tuple[str, str]], int]:
        lines: list[tuple[str, str]] = [
            (tr(self.lang, "help_title"), KIND_HEADER), ("", KIND_NORMAL)]
        for ln in HELP_TEXT.splitlines():
            lines.append((ln, KIND_NORMAL))
        lines.append(("", KIND_NORMAL))
        lines.append(("────────────────────────────────────────────────────────", KIND_FOCUS))
        return lines, -1

    # ---- columns -----------------------------------------------------------

    def column_items(self, col: int) -> list[str]:
        n = self.sel
        if col == 0:
            return [b.en for b in canon.BOOKS]
        if col == 1:
            return [str(c) for c in range(1, n.book().chapters + 1)]
        if col == 2:
            hi = _max_verse(n.book(), n.chapter) or 1
            return [str(v) for v in range(1, hi + 1)]
        vref = refs.Ref(n.book(), n.chapter, n.verse, n.chapter, n.verse)
        words = corpus.get_words(vref, ORIG["nt" if n.book().nt else "ot"])
        return [f"{_surface(w)} {w.strongs}" for w in words]

    def column_value(self, col: int) -> int:
        n = self.sel
        if col == 0:
            return n.book_idx + 1
        if col == 1:
            return n.chapter
        if col == 2:
            return n.verse
        return self.sel_word or 1

    def column_has_note(self, col: int, value: int) -> bool:
        n = self.sel
        osis = n.book().osis
        if col == 0:
            return notes.has_book_note(canon.BOOKS[value - 1].osis)
        if col == 1:
            return notes.has_chapter_note(osis, value)
        if col == 2:
            return notes.has_verse_note(osis, n.chapter, value)
        return notes.has_word_note(osis, n.chapter, n.verse, value)

    # ---- nav actions -------------------------------------------------------

    def _set_col_value(self, col: int, value: int):
        if col == 0:
            self.book_idx = value - 1
            self.chapter = 1
            self.verse = 1
            self.sel_word = 1
        elif col == 1:
            self.chapter = value
            self.verse = 1
            self.sel_word = 1
        elif col == 2:
            self.verse = value
            self.sel_word = 1
        else:
            self.sel_word = value
        self.sel = Node(self.book_idx, self.chapter, self.verse)

    def move_sel(self, delta: int):
        items = self.column_items(self.nav_col)
        if not items:
            return
        cur = self.column_value(self.nav_col)
        idx = cur - 1 + delta
        idx = max(0, min(len(items) - 1, idx))
        self._set_col_value(self.nav_col, idx + 1)

    def drill(self):
        if self.nav_col < 3:
            self.nav_col += 1

    def up(self):
        if self.nav_col > 0:
            self.nav_col -= 1

    def commit(self):
        node = Node(self.book_idx, self.chapter, self.verse)
        if self.nav_col == 3 and self.sel_word is not None:
            self.goto(node, view="word", word_idx=self.sel_word)
            self._enter_word_view()
        else:
            self.goto(node, view="verse", word_idx=None)
        # committing does NOT clear the bookmark (p sets/updates it)
        self.nav_visible = False
        self.message = ""

    def _enter_word_view(self):
        wref = refs.Ref(self.focus.book(), self.focus.chapter, self.focus.verse,
                        self.focus.chapter, self.focus.verse)
        words = corpus.get_words(wref, ORIG["nt" if self.focus.book().nt else "ot"])
        w = next((x for x in words if x.idx == self.word_idx), None)
        query = w.strongs if (w and w.strongs) else (w.lemma if w else "")
        self.word_result = search.word_occurrences(query) if query else {}
        occ = self.word_result.get("occurrences", [])
        cpos = -1
        for i, (ver, osis, ch, v, _s, _m) in enumerate(occ):
            if osis == self.focus.book().osis and ch == self.focus.chapter and v == self.focus.verse:
                cpos = i
                break
        self.word_cursor = cpos if cpos >= 0 else 0

    def exit_nav(self):
        self.book_idx = self.focus.book_idx
        self.chapter = self.focus.chapter
        self.verse = self.focus.verse
        self.sel_word = self.word_idx or 1
        self.sel = Node(self.book_idx, self.chapter, self.verse)
        self.nav_visible = False
        self.nav_col = 0

    def toggle_nav(self):
        if self.nav_visible:
            self.exit_nav()
        else:
            self.book_idx = self.focus.book_idx
            self.chapter = self.focus.chapter
            self.verse = self.focus.verse
            self.sel_word = self.word_idx or 1
            self.sel = Node(self.book_idx, self.chapter, self.verse)
            self.nav_visible = True
            self.nav_col = 0

    # ---- content actions ---------------------------------------------------

    def move_focus(self, delta: int):
        if self.view != "verse":
            return
        keys = self.verse_list()
        if not keys:
            return
        cur = (self.focus.chapter, self.focus.verse)
        try:
            i = keys.index(cur)
        except ValueError:
            i = 0
        i = max(0, min(len(keys) - 1, i + delta))
        ch, v = keys[i]
        self.goto(Node(self.focus.book_idx, ch, v), view="verse", word_idx=None)

    def move_word_cursor(self, delta: int):
        occ = self.word_result.get("occurrences", [])
        if not occ:
            return
        self.word_cursor = max(0, min(len(occ) - 1, self.word_cursor + delta))

    def jump_word_cursor(self):
        occ = self.word_result.get("occurrences", [])
        if not (0 <= self.word_cursor < len(occ)):
            return
        _ver, osis, ch, v, _s, _m = occ[self.word_cursor]
        self.goto(Node(_osis_index(osis), ch, v), view="verse", word_idx=None)
        self.nav_visible = False

    def exit_word_view(self):
        self.view = "verse"
        self.word_idx = None

    def move_result_cursor(self, delta: int):
        if not self.result_items:
            return
        self.result_cursor = max(0, min(len(self.result_items) - 1, self.result_cursor + delta))

    def jump_result_cursor(self):
        if not (0 <= self.result_cursor < len(self.result_items)):
            return
        bi, ch, v = self.result_items[self.result_cursor]
        self.goto(Node(bi, ch, v), view="verse", word_idx=None)
        self.nav_visible = False

    def exit_result_view(self):
        self.view = "verse"
        self.result_lines = []
        self.result_items = []
        self.result_cursor = 0

    def cycle_scope(self):
        i = SCOPES.index(self.scope)
        self.scope = SCOPES[(i + 1) % len(SCOPES)]

    def set_scope(self, name: str) -> bool:
        if name not in SCOPES:
            return False
        self.scope = name
        return True

    def resize_window(self, delta: int):
        self.window = max(1, min(40, self.window + delta))

    # ---- pin ---------------------------------------------------------------

    # ---- bookmark ---------------------------------------------------------
    # set_bookmark / back are defined above with the focus-change helpers.

    # ---- search-within-preview ---------------------------------------------

    def find(self, pattern: str) -> int:
        self.find_pat = pattern
        self.find_idx = -1
        if not pattern:
            self.find_hits = []
            return 0
        lines, _ = self.render_content()
        rx = re.compile(re.escape(pattern), re.IGNORECASE)
        self.find_hits = [i for i, (t, _k) in enumerate(lines) if rx.search(t)]
        if self.find_hits:
            self.find_idx = 0
        return len(self.find_hits)

    def find_next(self, delta: int) -> int:
        if not self.find_hits:
            return -1
        i = (self.find_idx + delta) % len(self.find_hits)
        self.find_idx = i
        return self.find_hits[i]

    # ---- notes / editor ----------------------------------------------------

    def begin_edit(self):
        if self.nav_visible:
            return
        target = self.focus_note_target()
        self.note_target = target
        text = self._load_note(target)
        self.note_lines = text.rstrip("\n").splitlines() or [""]
        self.note_cy = 0
        self.note_cx = 0
        self.note_dirty = False
        self.editing = True
        self._popup = (self.editor_mode == "popup")

    def end_edit(self, save: bool = True):
        if save and self.note_target:
            text = "\n".join(self.note_lines)
            self._save_note(self.note_target, text)
        self.editing = False
        self.note_target = ()
        self._popup = False

    def insert_char(self, ch):
        line = self.note_lines[self.note_cy]
        self.note_lines[self.note_cy] = line[:self.note_cx] + ch + line[self.note_cx:]
        self.note_cx += len(ch)
        self.note_dirty = True

    def insert_newline(self):
        line = self.note_lines[self.note_cy]
        before, after = line[:self.note_cx], line[self.note_cx:]
        self.note_lines[self.note_cy] = before
        self.note_lines.insert(self.note_cy + 1, after)
        self.note_cy += 1
        self.note_cx = 0
        self.note_dirty = True

    def backspace(self):
        if self.note_cx == 0:
            if self.note_cy == 0:
                return
            prev = self.note_lines[self.note_cy - 1]
            self.note_cx = len(prev)
            self.note_lines[self.note_cy - 1] = prev + self.note_lines[self.note_cy]
            del self.note_lines[self.note_cy]
            self.note_cy -= 1
        else:
            line = self.note_lines[self.note_cy]
            self.note_lines[self.note_cy] = line[:self.note_cx - 1] + line[self.note_cx:]
            self.note_cx -= 1
        self.note_dirty = True

    def cursor_move(self, dy: int, dx: int):
        cy, cx = self.note_cy, self.note_cx
        cy = max(0, min(len(self.note_lines) - 1, cy + dy))
        if dx:
            cx = max(0, min(len(self.note_lines[cy]), cx + dx))
        if dy != 0:
            cx = min(cx, len(self.note_lines[cy]))
        self.note_cy, self.note_cx = cy, cx

    # ---- commands ----------------------------------------------------------

    def execute(self, line: str) -> str:
        line = line.strip()
        if line.startswith(":"):
            line = line[1:].strip()
        if not line:
            return ""
        if line in ("q", "quit", "exit"):
            self.running = False
            return ""
        if line in ("help", "?"):
            self.show_help = True
            self.help_scroll = 0
            return ""
        parts = line.split(None, 1)
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        if cmd == "passage":
            return self._cmd_passage(arg)
        if cmd == "versions":
            return self._cmd_versions(arg)
        if cmd == "scope":
            return self._cmd_scope(arg)
        if cmd == "set":
            return self._cmd_set(arg)
        if cmd == "word":
            return self._cmd_word(arg)
        if cmd == "search":
            return self._cmd_search(arg)
        if cmd == "export":
            return self._cmd_export(arg)
        if cmd == "setup":
            self.open_intro()
            return ""
        return f"unknown command: {cmd} (try :help)"

    def _cmd_passage(self, arg: str) -> str:
        if not arg:
            self.study_set = None
            return tr(self.lang, "study_set_cleared")
        try:
            ref = refs.parse_ref(arg)
        except (refs.BadRef, canon.UnknownBook) as e:
            return tr(self.lang, "bad_ref", e=str(e))
        self.study_set = ref
        keys = self.verse_list()
        if keys:
            ch, v = keys[0]
        else:
            ch, v = ref.chapter, ref.verse
        self.goto(Node(_osis_index(ref.book.osis), ch, v), view="verse", word_idx=None)
        self.nav_visible = False
        return tr(self.lang, "study_set", ref=ref.en_label())

    def _cmd_versions(self, arg: str) -> str:
        if not arg:
            return tr(self.lang, "versions_set", vs=", ".join(self.effective_versions()))
        vs = [v.strip() for v in arg.split(",") if v.strip()]
        if not vs:
            return "no versions given"
        self.versions = vs
        self._versions_custom = True
        return tr(self.lang, "versions_set", vs=", ".join(vs))

    def _cmd_scope(self, arg: str) -> str:
        if self.set_scope(arg):
            return f"scope: {self.scope}"
        return tr(self.lang, "bad_scope", a=arg)

    def _cmd_set(self, arg: str) -> str:
        if not arg:
            self.open_settings()
            return ""
        kv = arg.split(None, 1)
        key = kv[0]
        val = kv[1] if len(kv) > 1 else ""
        if key == "highlight" and val in ("color", "minimal", "auto"):
            self.highlight = val
            self._persist_meta()
            return f"highlight: {val}"
        if key == "editor" and val in ("inline", "popup"):
            self.editor_mode = val
            self._persist_meta()
            return f"editor: {val}"
        if key == "window":
            try:
                self.window = max(1, min(40, int(val)))
                self._persist_meta()
                return f"window: {self.window}"
            except ValueError:
                return "window needs an integer"
        if key == "notemark":
            self.notemark = val[:2] or "✎"
            self._persist_meta()
            return f"notemark: {self.notemark!r}"
        return (f"unknown setting: {arg} (try :set highlight color|minimal, "
                ":set editor popup, :set window N, :set notemark <char>)")

    def _persist_meta(self):
        notes.write_meta({"highlight": self.highlight, "editor": self.editor_mode,
                           "window": self.window, "lang": self.lang,
                           "translations": list(self.translations),
                           "show_verse_marks": self.show_verse_marks,
                           "notemark": self.notemark})

    DEFAULT_SETTINGS = {"highlight": "auto", "editor_mode": "inline", "window": 5,
                        "lang": "en", "translations": ["cuvs", "asv"],
                        "show_verse_marks": True, "notemark": "✎",
                        "_versions_custom": False}

    def restore_defaults(self):
        """Reset every preference to its default (keeps setup_done; does NOT
        touch your notes or imported scripture)."""
        for k, v in self.DEFAULT_SETTINGS.items():
            setattr(self, k, list(v) if isinstance(v, list) else v)
        self._persist_meta()


    def _cmd_word(self, arg: str) -> str:
        if not arg:
            return "usage: :word <G3958 | lemma>"
        r = search.word_occurrences(arg)
        occ = r.get("occurrences", [])
        if not occ:
            return tr(self.lang, "no_occurrences", q=arg)
        self.result_title = f"word: {r.get('lemma','')} ({r.get('strongs','') or '?'}) — {r.get('gloss','')}"
        self.result_items = [(_osis_index(o[1]), o[2], o[3]) for o in occ]
        self.result_lines = self._format_word_results(r)
        self.result_cursor = 0
        self.view = "result"
        self.nav_visible = False
        return tr(self.lang, "occurrences_count", n=len(occ))

    def _format_word_results(self, r: dict) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = [(self.result_title, KIND_HEADER), ("", KIND_NOTE)]
        for i, (ver, osis, ch, v, surface, morph) in enumerate(r.get("occurrences", [])):
            mark = "▶" if i == 0 else " "
            out.append((f" {mark} {osis} {ch}:{v}  {surface}  ({search.greek_morph_label(morph)})",
                        KIND_OCCUR_SEL if i == 0 else KIND_OCCUR))
        return out

    def _cmd_search(self, arg: str) -> str:
        if not arg:
            return "usage: :search <pattern>"
        try:
            hits = search.search_text(arg, SEARCH_DEFAULT, lemma=False)
        except re.error as e:
            return f"bad pattern: {e}"
        if not hits:
            return tr(self.lang, "no_matches")
        self.result_title = f"search: {arg} — {len(hits)} hits"
        self.result_items = [(_osis_index(o[1]), o[2], o[3]) for o in hits]
        self.result_lines = [(self.result_title, KIND_HEADER), ("", KIND_NOTE)]
        for i, (ver, osis, ch, v, text) in enumerate(hits):
            mark = "▶" if i == 0 else " "
            self.result_lines.append((f" {mark} {osis} {ch}:{v}  {text}",
                                     KIND_OCCUR_SEL if i == 0 else KIND_OCCUR))
        self.result_cursor = 0
        self.view = "result"
        self.nav_visible = False
        return tr(self.lang, "matches_count", n=len(hits))

    def _cmd_export(self, arg: str) -> str:
        if not arg:
            return "usage: :export <ref>"
        try:
            ref = refs.parse_ref(arg)
        except (refs.BadRef, canon.UnknownBook) as e:
            return tr(self.lang, "bad_ref", e=str(e))
        body = notes.export_ref(ref, self.effective_versions())
        path = corpus.root() / "studies" / f"{ref.slug()}.md"
        if path.exists():
            path = corpus.root() / "studies" / f"{ref.slug()}.notes.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return tr(self.lang, "exported", p=str(path.relative_to(corpus.root())))


HELP_TEXT = """\
exeg TUI — keys
 NAV   Tab toggle nav · j/k move · l drill · h up · Enter commit · Esc exit
 VERSE j/k next/prev verse · z scope · +/- window · b back · p bookmark
 WORD  (in word view) j/k select occurrence · Enter jump · Esc back
 NOTES i edit note (Esc save) · :set editor popup for IME-safe input
 FIND  / search text · n/N next/prev
 CMDS  :passage <ref> · :versions <list> · :scope w|c|v
       :word <q> · :search <pat> · :export <ref> · :set … · :help · :q
"""


# --------------------------------------------------------------------------- #
# curses driver
# --------------------------------------------------------------------------- #

class Screen:
    def __init__(self):
        self.stdscr = None
        self.has_color = False

    def open(self):
        # ncurses otherwise waits about one second to distinguish a standalone
        # Escape press from the start of an arrow/function-key sequence.
        try:
            curses.set_escdelay(25)
        except (AttributeError, curses.error):
            pass
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.has_color = False
        if curses.has_colors():
            try:
                curses.start_color()
                self.has_color = True
                try:
                    self.has_color = curses.COLOR_PAIRS >= 8
                except AttributeError:
                    pass
                try:
                    curses.use_default_colors()
                except curses.error:
                    pass
                curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLUE)
                curses.init_pair(2, curses.COLOR_CYAN, -1)
                curses.init_pair(3, curses.COLOR_YELLOW, -1)
                curses.init_pair(4, curses.COLOR_GREEN, -1)
                curses.init_pair(5, curses.COLOR_BLUE, -1)
                curses.init_pair(6, curses.COLOR_MAGENTA, -1)
            except curses.error:
                self.has_color = False

    def suspend(self):
        try:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.curs_set(1)
        except curses.error:
            pass
        curses.endwin()

    def restore(self):
        self.open()

    def close(self):
        try:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()
        except Exception:
            pass


def _color_on(c: Controller, screen: Screen) -> bool:
    if c.highlight == "minimal":
        return False
    if c.highlight == "color":
        return True
    return screen.has_color


def _attr(kind: str, color: bool) -> int:
    if not color:
        if kind in (KIND_FOCUS, KIND_TITLE, KIND_TOKEN, KIND_OCCUR_SEL):
            return curses.A_BOLD
        if kind == KIND_DIM:
            return curses.A_DIM
        return curses.A_NORMAL
    if kind == KIND_FOCUS:
        return curses.A_BOLD | curses.color_pair(1)
    if kind == KIND_TITLE:
        return curses.A_BOLD | curses.color_pair(3)
    if kind == KIND_STATUS:
        return curses.color_pair(4)
    if kind == KIND_HEADER:
        return curses.A_BOLD | curses.color_pair(2)
    if kind == KIND_DIM:
        return curses.A_DIM
    if kind == KIND_COLHDR:
        return curses.A_BOLD | curses.color_pair(2)
    if kind == KIND_SEL:
        return curses.A_BOLD | curses.color_pair(5)
    if kind == KIND_TOKEN:
        return curses.A_BOLD | curses.color_pair(6)
    if kind == KIND_OCCUR_SEL:
        return curses.A_BOLD | curses.color_pair(5)
    if kind in (KIND_NOTE, KIND_MSG, KIND_LABEL):
        return curses.A_DIM
    return curses.A_NORMAL


def _marker(kind: str) -> str:
    return "▶ " if kind == KIND_FOCUS else "  "


def _char_cells(ch: str) -> int:
    """Return the terminal columns occupied by one Unicode code point."""
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Cf", "Mn", "Me"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _cell_width(text: str) -> int:
    return sum(_char_cells(ch) for ch in text)


def _slice_cells(text: str, max_cells: int) -> str:
    """Take the longest prefix that fits in ``max_cells`` terminal columns."""
    out = []
    used = 0
    for ch in text:
        cells = _char_cells(ch)
        if used + cells > max_cells:
            break
        out.append(ch)
        used += cells
    return "".join(out)


def _put(win, y, x, s, attr, maxw):
    if x >= maxw:
        return
    s = _slice_cells(s, max(0, maxw - x - 1))
    if not s:
        return
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass


def run(controller: Controller | None = None) -> int:
    if controller is None:
        controller = Controller()
    screen = Screen()
    try:
        screen.open()
    except Exception as e:
        print(f"cannot start TUI: {e}\nuse `exeg passage/word/search` instead.",
              file=sys.stderr)
        return 1
    scroll = 0
    try:
        while controller.running:
            color = _color_on(controller, screen)
            if controller.editing and getattr(controller, "_popup", False):
                _edit_popup(screen, controller)
                continue
            lines, focus_line = controller.render_content()
            if controller.find_hits and controller.find_idx >= 0:
                lines = _apply_find(lines, controller)
            screen.stdscr.erase()
            h, w = screen.stdscr.getmaxyx()
            _put(screen.stdscr, 0, 0, _title(controller), _attr(KIND_TITLE, color), w)
            top, bottom = 1, h - 1
            body_h = bottom - top
            if controller.intro:
                scroll = _draw_lines(screen, lines, top, body_h, 0, w, 0, color)
            elif controller.show_help:
                controller.help_scroll = _draw_lines(
                    screen, lines, top, body_h, 0, w, controller.help_scroll, color)
                scroll = controller.help_scroll
            elif controller.editing:
                # scripture on top (~60%), editor pane at the bottom (~40%)
                editor_h = max(3, (body_h * 2) // 5)
                verse_h = body_h - editor_h - 1   # -1 for the divider line
                scroll = _draw_lines(screen, lines, top, verse_h, 0, w,
                                     scroll, color, focus_line)
                _put(screen.stdscr, top + verse_h, 0, "─" * w,
                      _attr(KIND_COLHDR, color), w)
                ed = controller.editor_lines()
                _draw_lines(screen, ed, top + verse_h + 1, editor_h, 0, w, 0, color, wrap=False)
            elif controller.nav_visible:
                _draw_nav(screen, controller, top, body_h, w, color)
                nav_w = _nav_widths(w)[1]
                # word-wrap the preview just like the full-pane view; the nav
                # columns are a separate pane and scroll independently
                scroll = _draw_lines(screen, lines, top, body_h, nav_w, w,
                                     scroll, color, focus_line, wrap=True)
            else:
                scroll = _draw_pane(screen, controller, lines, focus_line, top,
                                    body_h, 0, w, scroll, color)
            _put(screen.stdscr, h - 1, 0, _status(controller), _attr(KIND_STATUS, color), w)
            if controller.editing and not controller.show_help:
                _position_editor_cursor(screen, controller, top, verse_h, w)
            else:
                try:
                    curses.curs_set(0)
                except curses.error:
                    pass
            screen.stdscr.refresh()
            if controller.editing and not controller.show_help \
                    and not getattr(controller, "_popup", False):
                _edit_loop(screen, controller)
            else:
                try:
                    key = screen.stdscr.getch()
                except KeyboardInterrupt:
                    key = 3  # Ctrl-C: delivered as a key, not a crash
                scroll = _handle(screen, controller, key, scroll, lines, focus_line, body_h)
                if getattr(controller, "find_target_line", None) is not None:
                    px = _nav_widths(w)[1] if controller.nav_visible else 0
                    row = _line_to_row(lines, controller.find_target_line, max(8, w - px), color)
                    if row >= 0:
                        scroll = row
                    controller.find_target_line = None
                if getattr(controller, "_pending_apikey", None):
                    env_var, label = controller._pending_apikey
                    controller._pending_apikey = None
                    _prompt_api_key(screen, controller, env_var, label)
                if getattr(controller, "_pending_setup", False):
                    controller._pending_setup = False
                    _run_setup_wizard(screen, controller)
                if getattr(controller, "_pending_restore", False):
                    controller._pending_restore = False
                    _confirm_restore(screen, controller)
                if getattr(controller, "_pending_optional_fetch", False):
                    controller._pending_optional_fetch = False
                    _run_optional_fetch(screen, controller)
    finally:
        screen.close()
    return 0


def _run_optional_fetch(screen, c: Controller):
    """Suspend curses while downloading the idempotent public study pack."""
    from exeg import fetch
    screen.suspend()
    print("\nexeg — optional study data")
    print("=" * 40)
    try:
        fetch.fetch_optional_pack(log=lambda msg: print(f"  {msg}"))
        print("\n  download complete")
    except Exception as e:
        print(f"\n  download stopped: {e}")
        print("  completed datasets were kept; select Download again to retry.")
    try:
        input("  press Enter to return... ")
    except (EOFError, KeyboardInterrupt):
        pass
    screen.restore()


def _confirm_restore(screen, c: Controller):
    """Suspend curses, ask 'yes' to confirm wiping all settings to defaults."""
    screen.suspend()
    print("\n↺ Restore all settings to defaults")
    print("  This resets language, translations, highlight, editor, window size,")
    print("  verse-note marks and mark glyph to their defaults.")
    print("  Your NOTES and any imported scripture are NOT touched.")
    try:
        ans = input("  Type 'yes' to confirm (anything else cancels): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans == "yes":
        c.restore_defaults()
        print("  settings restored to defaults.")
    else:
        print("  cancelled — no changes.")
    try:
        input("  press Enter to return... ")
    except (EOFError, KeyboardInterrupt):
        pass
    screen.restore()


def _apply_find(lines, c: Controller) -> list[tuple[str, str]]:
    if not c.find_pat:
        return lines
    out = []
    cur = c.find_hits[c.find_idx] if 0 <= c.find_idx < len(c.find_hits) else -1
    for i, (t, k) in enumerate(lines):
        if i == cur:
            out.append((">> " + t, KIND_FOCUS))
        elif i in c.find_hits:
            out.append((t, KIND_FOCUS if k == KIND_NORMAL else k))
        else:
            out.append((t, k))
    return out


def _title(c: Controller) -> str:
    if c.intro:
        return " exeg — first-run setup "
    n = c.shown()
    b = n.book()
    extra = ""
    if c.view == "word" and c.word_idx is not None:
        extra = " · word"
    elif c.view == "result":
        extra = " · " + c.result_title
    crumb = f"{b.en} › {n.chapter} › v.{n.verse}"
    if c.view == "word":
        crumb += f" › #{c.word_idx}"
    ind = " · focus ✎"
    if c.bookmark is not None:
        bn, bv, bw = c.bookmark
        ind += f" · bm:{bn.book().en} {bn.chapter}:{bn.verse}"
    if c.study_set is not None:
        ind += " · set:" + c.study_set.en_label()
    if c.editing:
        ind += " · INSERT"
    return f" exeg · {crumb} · scope:{c.scope}{extra}{' ±'+str(c.window) if c.scope=='window' else ''}{ind} "


def _status(c: Controller) -> str:
    if c.intro:
        return " first-run setup · j/k move · Enter select · Begin to start "
    if c.editing:
        return tr(c.lang, "insert_status")
    mode = "NAV" if c.nav_visible else ("WORD" if c.view == "word" else
                                        ("RESULT" if c.view == "result" else
                                         ("SETTINGS" if c.view == "settings" else "NORMAL")))
    hint = {
        "NAV": tr(c.lang, "nav_hint"),
        "NORMAL": tr(c.lang, "normal_hint"),
        "WORD": tr(c.lang, "word_hint"),
        "RESULT": tr(c.lang, "result_hint"),
        "SETTINGS": tr(c.lang, "settings_title"),
    }[mode]
    msg = (c.message + " · ") if c.message else ""
    return f" {msg}{mode} · {hint}"


def _nav_widths(w: int) -> tuple[list[int], int]:
    cw = [min(14, max(10, w // 10)), 5, 5, 14]
    total = sum(cw) + len(cw)
    if total > w - 16:
        cw = [max(7, w // 9), 4, 4, 11]
        total = sum(cw) + len(cw)
    return cw, total


def _draw_nav(screen, c: Controller, top: int, body_h: int, w: int, color: bool):
    cw, total = _nav_widths(w)
    colnames = [tr(c.lang, "col_books"), tr(c.lang, "col_ch"), tr(c.lang, "col_vs"), tr(c.lang, "col_words")]
    x = 0
    for i, name in enumerate(colnames):
        _put(screen.stdscr, top, x, name[:cw[i]].ljust(cw[i]),
              _attr(KIND_COLHDR, color), w)
        items = c.column_items(i)
        val = c.column_value(i)
        active = (i == c.nav_col)
        sel_row = val - 1
        start = max(0, sel_row - body_h // 2 + 1) if active else 0
        for r in range(body_h - 1):
            idx = start + r
            if idx >= len(items):
                break
            row = top + 1 + r
            text = items[idx]
            mark = c.notemark if c.column_has_note(i, idx + 1) else " "
            label = f"{mark}{text}"[:cw[i]].ljust(cw[i])
            if idx == sel_row and active:
                _put(screen.stdscr, row, x, label, _attr(KIND_SEL, color), w)
            elif idx == sel_row:
                _put(screen.stdscr, row, x, label, curses.A_BOLD, w)
            else:
                _put(screen.stdscr, row, x, label, _attr(KIND_ITEM, color), w)
        x += cw[i] + 1



def _pad_cells(text: str, width: int) -> str:
    clipped = _slice_cells(text, width)
    return clipped + " " * max(0, width - _cell_width(clipped))


def _version_line(label: str, body: str) -> str:
    """Format every translation body at the same terminal-cell column."""
    return f"  {_pad_cells(label, 7)} {body}"


def _wrap_plain(text: str, width: int) -> list[str]:
    if not text:
        return [""]
    width = max(1, width)
    rows = []
    remaining = text
    while _cell_width(remaining) > width:
        prefix = _slice_cells(remaining, width)
        cut = len(prefix)
        if cut == 0:  # a double-width character in a one-column area
            prefix, cut = remaining[0], 1

        # If the cell boundary splits a word that would fit on its own, wrap
        # before that word. Truly long words (including unspaced CJK text) are
        # split at the cell boundary instead.
        if (cut < len(remaining) and not remaining[cut - 1].isspace()
                and not remaining[cut].isspace()):
            word_start = cut
            while word_start > 0 and not remaining[word_start - 1].isspace():
                word_start -= 1
            word_end = cut
            while word_end < len(remaining) and not remaining[word_end].isspace():
                word_end += 1
            word = remaining[word_start:word_end]
            before = remaining[:word_start]
            # Whitespace-delimited Latin/Greek words stay intact. East Asian
            # runs remain breakable between characters, even when the source
            # contains an internal space (common around divine names in CUVS).
            has_wide_chars = any(_char_cells(ch) == 2 for ch in word)
            if before.strip() and _cell_width(word) <= width and not has_wide_chars:
                prefix = before.rstrip()
                cut = word_start

        rows.append(prefix.rstrip())
        remaining = remaining[cut:].lstrip()
    rows.append(remaining)
    return rows


def _wrap_one(text, width):
    """Cell-aware wrapping with a hanging indent for translation bodies."""
    width = max(1, width)
    match = re.match(r"^(  \S+ {2,})(\S.*)$", text)
    if match:
        prefix, body = match.groups()
        indent_width = _cell_width(prefix)
        if indent_width < width:
            body_rows = _wrap_plain(body, width - indent_width)
            indent = " " * indent_width
            return [prefix + body_rows[0]] + [indent + row for row in body_rows[1:]]
    return _wrap_plain(text, width)


def _build_rows(lines, avail, color, wrap=True):
    """Turn logical lines into display rows, word-wrapping each to `avail`.
    Returns (rows, line_row) where line_row[i] is the starting row of line i."""
    rows = []
    line_row = []
    for text, kind in lines:
        line_row.append(len(rows))
        marker = _marker(kind) if (not color and kind == KIND_FOCUS) else ""
        if wrap and _cell_width(text) + _cell_width(marker) > avail:
            chunks = _wrap_one(text, max(4, avail - _cell_width(marker)))
        else:
            chunks = [text]
        for ci, ch in enumerate(chunks):
            m = marker if ci == 0 else " " * len(marker)
            rows.append((m + ch, kind))
    return rows, line_row


def _draw_lines(screen, lines, top, height, x, w, scroll, color, focus_line=-1, wrap=True):
    """Draw up to `height` rows of `lines` (word-wrapped) starting at row `top`."""
    avail = max(8, w - x)
    rows, line_row = _build_rows(lines, avail, color, wrap)
    focus_row = line_row[focus_line] if 0 <= focus_line < len(line_row) else -1
    if focus_row >= 0:
        if focus_row < scroll:
            scroll = focus_row
        elif focus_row >= scroll + height:
            scroll = focus_row - height + 1
    scroll = max(0, min(scroll, max(0, len(rows) - height)))
    for r in range(height):
        idx = scroll + r
        if idx >= len(rows):
            break
        text, kind = rows[idx]
        _put(screen.stdscr, top + r, x, text, _attr(kind, color), w)
    return scroll


def _line_to_row(lines, line_idx, avail, color, wrap=True):
    if line_idx < 0:
        return -1
    _, line_row = _build_rows(lines, avail, color, wrap)
    return line_row[line_idx] if line_idx < len(line_row) else -1


def _draw_pane(screen, c, lines, focus_line, top, body_h, x, w, scroll, color):
    return _draw_lines(screen, lines, top, body_h, x, w, scroll, color, focus_line, wrap=True)


def _position_editor_cursor(screen, c: Controller, top, verse_h, w):
    # editor pane starts after the divider; content begins 2 lines in (header + blank)
    row = top + verse_h + 1 + 2 + c.note_cy
    col = c.note_cx
    h, ww = screen.stdscr.getmaxyx()
    if 0 <= row < h - 1:
        try:
            curses.curs_set(1)
            screen.stdscr.move(row, min(col, ww - 1))
        except curses.error:
            pass


def _edit_loop(screen, c: Controller):
    try:
        ch = screen.stdscr.get_wch()
    except KeyboardInterrupt:
        ch = 3  # Ctrl-C
    except Exception:
        ch = screen.stdscr.getch()
    if isinstance(ch, str):
        if ch == "\x1b":
            c.end_edit(save=True)
        elif ch in ("\r", "\n"):
            c.insert_newline()
        elif ch in ("\x7f", "\b", "\x08"):
            c.backspace()
        elif ch.isprintable() or ch == "\t":
            c.insert_char(ch)
        return
    if ch == 27:
        c.end_edit(save=True)
    elif ch in (curses.KEY_ENTER, 10, 13):
        c.insert_newline()
    elif ch in (curses.KEY_BACKSPACE, 8, 127, 263):
        c.backspace()
    elif ch == curses.KEY_LEFT:
        c.cursor_move(0, -1)
    elif ch == curses.KEY_RIGHT:
        c.cursor_move(0, 1)
    elif ch == curses.KEY_UP:
        c.cursor_move(-1, 0)
    elif ch == curses.KEY_DOWN:
        c.cursor_move(1, 0)
    elif ch == 3:  # Ctrl-C
        c.end_edit(save=False)


def _prompt_api_key(screen, c: Controller, env_var: str, label: str):
    """Suspend curses, paste one API key with masked input, write to .env."""
    import getpass
    from exeg import setup
    screen.suspend()
    print(f"\n{label}")
    print("  (paste the key — input is hidden · Enter to save · Ctrl-C to skip)")
    try:
        val = getpass.getpass("  paste: ").strip()
    except (EOFError, KeyboardInterrupt):
        val = ""
        print("  skipped")
    if val:
        setup.write_env_key(env_var, val)
        os.environ[env_var] = val
        print(f"  saved {env_var} to .env")
    else:
        print("  (no change)")
    try:
        input("  press Enter to return... ")
    except (EOFError, KeyboardInterrupt):
        pass
    screen.restore()


def _run_setup_wizard(screen, c: Controller):
    """Suspend curses and run the full onboarding wizard (language + keys)."""
    from exeg import setup
    screen.suspend()
    try:
        setup.run_setup(lang=None, only_keys=False)
        # pick up the chosen language for this session
        c.lang = notes.read_meta().get("lang", c.lang)
    except KeyboardInterrupt:
        print("\nsetup cancelled")
    input("  press Enter to return to the TUI... ")
    screen.restore()


def _edit_popup(screen, c: Controller):
    screen.suspend()
    target = c.note_target
    print(f"--- note ({target[0]}) · Ctrl-D to finish, Ctrl-C to cancel ---")
    existing = c._load_note(target) if not c.note_dirty else "\n".join(c.note_lines)
    if existing:
        print("current (edit below; blank submission keeps it):")
        print(existing)
    lines = []
    try:
        while True:
            ln = input()
            lines.append(ln)
    except EOFError:
        pass
    except KeyboardInterrupt:
        screen.restore()
        c.editing = False
        c._popup = False
        return
    screen.restore()
    if lines and not (len(lines) == 1 and lines[0] == ""):
        c.note_lines = lines
        c.end_edit(save=True)
    else:
        c.editing = False
        c._popup = False


def _handle(screen, c: Controller, key, scroll, lines, focus_line, body_h) -> int:
    k = key
    if k == curses.KEY_RESIZE:
        return 0
    if c.intro:
        if k in (ord("j"), curses.KEY_DOWN):
            c.move_intro_cursor(1)
        elif k in (ord("k"), curses.KEY_UP):
            c.move_intro_cursor(-1)
        elif k in (10, 13, curses.KEY_ENTER, ord(" ")):
            c.toggle_intro()
        elif k == 27:
            c.finish_intro()
        return 0
    # help overlay: scroll with j/k, close with ? / q / Esc
    if c.show_help:
        if k in (ord("q"), 27):
            c.show_help = False
        elif k in (ord("j"), curses.KEY_DOWN, 4, 10, 13):
            c.help_scroll += 1
        elif k in (ord("k"), curses.KEY_UP, 21):
            c.help_scroll = max(0, c.help_scroll - 1)
        # any other key is ignored (does NOT dismiss)
        return 0
    c.message = ""
    if k == 3:  # Ctrl-C in normal mode: never crash; just stay
        return scroll
    if k == ord(":"):
        screen.suspend()
        try:
            line = input(":")
        except (EOFError, KeyboardInterrupt):
            line = ""
        screen.restore()
        msg = c.execute(line)
        if msg:
            c.message = msg
        return 0
    if k == ord("/"):
        screen.suspend()
        try:
            pat = input("/")
        except (EOFError, KeyboardInterrupt):
            pat = ""
        screen.restore()
        n = c.find(pat)
        c.message = f"/{pat}: {n} hits" if pat else "find cleared"
        c.find_target_line = c.find_hits[c.find_idx] if c.find_hits else None
        return 0
    if k == ord("n"):
        if c.find_hits:
            c.find_target_line = c.find_next(1)
        return 0
    if k == ord("N"):
        if c.find_hits:
            c.find_target_line = c.find_next(-1)
        return 0
    if k in (9,):  # Tab
        c.toggle_nav()
        return 0
    if k == 63 or (hasattr(curses, "KEY_F0") and k == curses.KEY_F0 + 1):  # "?" or F1
        if not c.show_help:
            c.show_help = True
            c.help_scroll = 0
            c.message = tr(c.lang, "help_open")
        return 0
    if k == ord("q"):
        if c.nav_visible:
            c.exit_nav()
        elif c.view == "settings":
            c.close_settings()
        elif c.view in ("word", "result"):
            c.exit_word_view() if c.view == "word" else c.exit_result_view()
        else:
            c.running = False
        return 0
    if c.nav_visible:
        if k == ord("l") or k == curses.KEY_RIGHT:
            c.drill()
        elif k == ord("h") or k == curses.KEY_LEFT:
            c.up()
        elif k in (10, 13, curses.KEY_ENTER):
            c.commit()
        elif k == 27:
            c.exit_nav()
        elif k in (ord("j"), curses.KEY_DOWN):
            c.move_sel(1)
        elif k in (ord("k"), curses.KEY_UP):
            c.move_sel(-1)
        elif k == ord("g"):
            c._set_col_value(c.nav_col, 1)
            c.sel = Node(c.book_idx, c.chapter, c.verse)
        elif k == ord("G"):
            items = c.column_items(c.nav_col)
            c._set_col_value(c.nav_col, len(items))
            c.sel = Node(c.book_idx, c.chapter, c.verse)
        return 0
    if c.editing:
        return 0
    if c.view == "settings":
        if k in (ord("j"), curses.KEY_DOWN):
            c.move_settings_cursor(1)
        elif k in (ord("k"), curses.KEY_UP):
            c.move_settings_cursor(-1)
        elif k in (10, 13, curses.KEY_ENTER, ord(" ")):
            c.toggle_settings()
        elif k == 27 or k == ord("h"):
            c.close_settings()
        elif k == ord("o"):
            c.close_settings()
        return 0
    if c.view == "word":
        if k in (ord("j"), curses.KEY_DOWN):
            c.move_word_cursor(1)
        elif k in (ord("k"), curses.KEY_UP):
            c.move_word_cursor(-1)
        elif k in (10, 13, curses.KEY_ENTER):
            c.jump_word_cursor()
        elif k == 27 or k == ord("h"):
            c.exit_word_view()
        elif k == ord("z"):
            c.cycle_scope()
        elif k == ord("i"):
            c.begin_edit()
        return 0
    if c.view == "result":
        if k in (ord("j"), curses.KEY_DOWN):
            c.move_result_cursor(1)
        elif k in (ord("k"), curses.KEY_UP):
            c.move_result_cursor(-1)
        elif k in (10, 13, curses.KEY_ENTER):
            c.jump_result_cursor()
        elif k == 27 or k == ord("h"):
            c.exit_result_view()
        return 0
    # verse view
    if k in (ord("j"), curses.KEY_DOWN):
        c.move_focus(1)
        return 0
    if k in (ord("k"), curses.KEY_UP):
        c.move_focus(-1)
        return 0
    if k == ord("z"):
        c.cycle_scope()
        return 0
    if k in (ord("+"), ord("=")):
        c.resize_window(1)
        return 0
    if k == ord("-"):
        c.resize_window(-1)
        return 0
    if k == ord("i"):
        c.begin_edit()
        return 0
    if k == ord("o"):
        c.open_settings()
        return 0
    if k == ord("p"):
        c.set_bookmark()
        return 0
    if k == ord("b"):
        c.back()
        return 0
    if k == ord("g"):
        keys = c.verse_list()
        if keys:
            ch, v = keys[0]
            c.goto(Node(c.focus.book_idx, ch, v), view="verse", word_idx=None)
        return 0
    if k == ord("G"):
        keys = c.verse_list()
        if keys:
            ch, v = keys[-1]
            c.goto(Node(c.focus.book_idx, ch, v), view="verse", word_idx=None)
        return 0
    if k == 4:  # Ctrl-d
        return scroll + max(1, body_h // 2)
    if k == 21:  # Ctrl-u
        return scroll - max(1, body_h // 2)
    return scroll


def cmd_tui(args) -> int:
    versions = args.versions.split(",") if getattr(args, "versions", None) else None
    return run(Controller(versions=versions))