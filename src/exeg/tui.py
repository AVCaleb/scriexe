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
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field

from exeg import canon, corpus, display, notes, refs, search
from exeg.i18n import tr

ORIG = {"nt": "sblgnt", "ot": "wlc"}
LOCAL_DEFAULT = ["cuvs", "asv"]

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
RTL_PREFIX = "rtl:"


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


@dataclass
class LineEditor:
    """Pure one-line editor used by the curses command and find prompts."""
    text: str = ""
    history: list[str] = field(default_factory=list)
    cursor: int = field(init=False)
    history_pos: int = field(init=False)
    draft: str = field(init=False)

    def __post_init__(self):
        self.cursor = len(self.text)
        self.history_pos = len(self.history)
        self.draft = self.text

    def _set_text(self, text: str) -> None:
        self.text = text
        self.cursor = len(text)

    def handle(self, key) -> str | None:
        if key in (10, 13, "\n", "\r", curses.KEY_ENTER):
            if self.text.strip() and (not self.history or self.history[-1] != self.text):
                self.history.append(self.text)
            return "submit"
        if key in (27, 3, "\x1b", "\x03"):
            return "cancel"
        if key in (curses.KEY_LEFT,):
            self.cursor = max(0, self.cursor - 1)
        elif key in (curses.KEY_RIGHT,):
            self.cursor = min(len(self.text), self.cursor + 1)
        elif key in (curses.KEY_HOME, 1, "\x01"):
            self.cursor = 0
        elif key in (curses.KEY_END, 5, "\x05"):
            self.cursor = len(self.text)
        elif key in (curses.KEY_BACKSPACE, 8, 127, "\b", "\x7f"):
            if self.cursor:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
        elif key == curses.KEY_DC:
            if self.cursor < len(self.text):
                self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        elif key in (21, "\x15"):  # Ctrl-U
            self.text = self.text[self.cursor:]
            self.cursor = 0
        elif key in (11, "\x0b"):  # Ctrl-K
            self.text = self.text[:self.cursor]
        elif key == curses.KEY_UP:
            if self.history and self.history_pos > 0:
                if self.history_pos == len(self.history):
                    self.draft = self.text
                self.history_pos -= 1
                self._set_text(self.history[self.history_pos])
        elif key == curses.KEY_DOWN:
            if self.history_pos < len(self.history) - 1:
                self.history_pos += 1
                self._set_text(self.history[self.history_pos])
            elif self.history_pos == len(self.history) - 1:
                self.history_pos = len(self.history)
                self._set_text(self.draft)
        elif isinstance(key, str) and key.isprintable():
            self.text = self.text[:self.cursor] + key + self.text[self.cursor:]
            self.cursor += len(key)
        return None


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
        self.suppress_focus_once = False
        self.command_history: list[str] = []
        self.find_history: list[str] = []

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
        self.clear_find()
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
        self.clear_find()
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
            return self._render_results()
        if self.view == "settings":
            return self.render_settings()
        if self.view == "word":
            return self._render_word()
        return self._render_verse()

    def _render_results(self) -> tuple[list[tuple[str, str]], int]:
        if not self.result_items:
            return list(self.result_lines), -1
        out = list(self.result_lines[:2])
        for i, (text, _kind) in enumerate(self.result_lines[2:]):
            selected = i == self.result_cursor
            out.append((f" {'▶' if selected else ' '} {text}",
                        KIND_OCCUR_SEL if selected else KIND_OCCUR))
        return out, 2 + self.result_cursor

    def _result_focus_line(self) -> int:
        return 2 + self.result_cursor if self.result_items else -1

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
                kind = (KIND_FOCUS if is_focus else
                        (KIND_DIM if self.scope == "window" else KIND_NORMAL))
                if version == "wlc":
                    kind = RTL_PREFIX + kind
                lines.append((_version_line(label, body), kind))
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
            original = ORIG["nt" if b.nt else "ot"]
            label = display.LABELS.get(original, "ORIG")
            kind = RTL_PREFIX + KIND_TOKEN if original == "wlc" else KIND_TOKEN
            lines.append((_version_line(label, " ".join(toks)), kind))
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
        lines.extend(help_lines(self.lang))
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
        self.clear_find()
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

    def find_allowed(self) -> bool:
        return (not self.intro and not self.show_help and not self.editing
                and not self.nav_visible and self.view == "verse")

    def clear_find(self, suppress_focus: bool = False) -> None:
        self.find_pat = ""
        self.find_hits = []
        self.find_idx = -1
        self.find_target_line = None
        self.suppress_focus_once = suppress_focus

    def find(self, pattern: str) -> int:
        if not self.find_allowed():
            self.clear_find()
            return 0
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
        self.clear_find()
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
        for ver, osis, ch, v, surface, morph in r.get("occurrences", []):
            out.append((f"[{ver.upper()}] {osis} {ch}:{v}  {surface}  "
                        f"({search.greek_morph_label(morph)})", KIND_OCCUR))
        return out

    def _cmd_search(self, arg: str) -> str:
        if not arg:
            return "usage: :search <pattern>"
        versions = [version for version in self.effective_versions()
                    if corpus.has_version(version)]
        try:
            hits = search.search_text(arg, versions, lemma=False)
        except re.error as e:
            return f"bad pattern: {e}"
        if not hits:
            return tr(self.lang, "no_matches")
        self.result_title = f"search: {arg} — {len(hits)} hits"
        self.result_items = [(_osis_index(o[1]), o[2], o[3]) for o in hits]
        self.result_lines = [(self.result_title, KIND_HEADER), ("", KIND_NOTE)]
        for ver, osis, ch, v, text in hits:
            self.result_lines.append((f"[{ver.upper()}] {osis} {ch}:{v}  {text}",
                                     KIND_OCCUR))
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
        path = corpus.studies_dir() / f"{ref.slug()}.md"
        if path.exists():
            path = corpus.studies_dir() / f"{ref.slug()}.notes.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return tr(self.lang, "exported", p=str(path.resolve()))


HELP_MANUAL = {
    "en": """\
exeg TUI — keys
 NAV   Tab toggle nav · j/k move · l drill · h up · Enter commit · Esc exit
 VERSE j/k next/prev verse · z scope · +/- window · b back · p bookmark
 WORD  (in word view) j/k select occurrence · Enter jump · Esc back
 NOTES i edit note (Esc save) · :set editor popup for IME-safe input
 FIND  / find in verse preview · j/k next/prev · Enter accept · Esc clear
 CMDS  :passage <ref> · :versions <list> · :scope window|chapter|verse
       :word <q> · :search <regex> · :export <ref> · :set … · :help · :q

# Detailed help
This manual describes what each mode and command changes. Scroll with j/k, the arrow keys, Enter, Ctrl-D, or Ctrl-U. Press q or Esc to close Help.

# Navigator
Press Tab to open the four-column navigator: Books, Chapters, Verses, and Words. Moving a selection updates the preview immediately but does not change the committed reading position until you press Enter.
$ j / k or Up / Down     move within the active column
$ l / Right              drill into the next column
$ h / Left               return to the previous column
$ g / G                  jump to the first / last item in the active column
$ Enter                  commit the selected verse or word
$ Esc or q               close NAV and return to the committed position
The Words column requires the optional SBLGNT or WLC original-language data; Strong's data enriches its lexical details. Install the study pack from onboarding or Settings if the column is empty.

# Reading scopes
The scope controls how much text surrounds the focused verse. Press z to cycle through the three modes.
$ window   show verses before and after the focus; + and - change the radius
$ chapter  show the complete chapter
$ verse    show only the focused verse and its attached note area
In reading mode, j/k moves the focused verse. g/G jumps to the first/last verse in the current study set. Ctrl-D and Ctrl-U scroll by half a screen without changing the focused verse.
WLC Hebrew scripture body rows align to the pane's right edge; version labels and all other translations remain left-aligned.

# Word study
From NAV, drill into Words and press Enter on a Greek or Hebrew form. The word view shows the selected form in context, its lemma/Strong's information when available, morphology, and occurrences in the installed corpus.
$ j / k       select an occurrence
$ Enter       open the selected occurrence in its verse
$ Esc or h    return to the verse view
You can also open a result list directly with :word. Original-language and Strong's datasets must be installed first.

# Notes
Close NAV, focus a verse, and press i to edit its note. In word view, i edits a note attached to that word occurrence instead.
$ Esc          save and leave the inline editor
$ Ctrl-C       discard this editing session
$ Arrow keys   move the inline editor cursor
Notes are stored as local Markdown files. A pencil mark identifies verses that already have notes.
For IME-heavy Chinese input, use :set editor popup. The popup editor accepts normal terminal input; press Ctrl-D to finish or Ctrl-C to cancel. A blank submission keeps the existing note.

# Find in preview
Press / in ordinary verse view with NAV closed to search the currently rendered translations and visible notes. This is a literal, case-insensitive search rather than a regular expression. It never searches old Results, Help, Settings, Word, or NAV content.
$ j / Down    move to the next match
$ k / Up      move to the previous match
$ Enter       accept the current viewport and clear highlighting
$ Esc         clear find and resume normal verse navigation
Submitting an empty pattern also clears find.

# Corpus search
:search performs a regular-expression search across the currently enabled versions that are installed locally. Every row identifies its source, such as [ASV] or [CUVS]. This is broader than /, which searches only the current verse preview.
$ :search hope
$ :search faith|hope
In Results, use j/k to move the visible selection, Enter to open that verse, and Esc or h to return to the pre-search verse.

# Bookmark
Press p in verse view to save the current location. There is one bookmark: pressing p again replaces it. Press b to return to it; returning also closes NAV. The title shows bm:<reference> while a bookmark exists.
A bookmark is useful before following a word occurrence or moving to another passage. It lasts for the current application session.

# Settings
Press o in verse view, or run :set with no argument, to open Settings. Use j/k to move, Enter or Space to toggle, and Esc to return.
Settings controls interface language, visible translations, API keys, note markers, optional study data, and restoration of defaults. Translation and display choices are persisted locally.
The “Download all optional study data” action installs SBLGNT, WLC, Strong's, WEB, KJV, and Vulgate. Completed datasets are kept if a download is interrupted; run the action again to retry.

# Command reference
From NAV, reading, Word, Results, or Settings, press : to enter a command. The leading colon shown below is optional after the prompt has opened. The prompt stays inside the TUI and keeps a session history.
$ Up / Down             previous / next command
$ Left / Right          move the cursor
$ Home / Ctrl-A         move to the start
$ End / Ctrl-E          move to the end
$ Backspace / Delete    delete before / at the cursor
$ Ctrl-U / Ctrl-K       delete start-to-cursor / cursor-to-end
$ Enter                 execute
$ Esc / Ctrl-C          cancel

$ :passage <ref>
Create a temporary study set and jump to its first verse. English and Chinese references are accepted. Running :passage with no reference clears the set and returns navigation to the current chapter.
$ Example: :passage Titus 1:1-4
$ Example: :passage 彼前3:13-16

$ :versions <comma-list>
Use an explicit version list for the current session. Version ids include cuvs, asv, web, kjv, vulgate, sblgnt, wlc, esv, and nasb95. This command overrides automatic original-language selection but does not replace the persisted Settings list.
$ Example: :versions cuvs,asv
Running :versions without a list reports the effective versions.

$ :scope window|chapter|verse
Set the reading scope directly instead of cycling with z. The scope is session state.
$ Example: :scope chapter

$ :word <Strong's number or lemma>
Search installed original-language data and open an occurrence list.
$ Example: :word G3958
If no study data or matching occurrence exists, the status line reports that no occurrence was found.

$ :search <regex>
Search the currently enabled, locally installed versions with a regular expression and open the result list. Use / instead when you only want to find literal text in the current preview.
$ Example: :search hope

# Export
:export compiles a selected passage, the currently effective translations, and attached book/chapter/verse/word notes into Markdown. After every export, the status line reports the complete absolute file path.
$ :export Titus 1:1-4
$ → studies/titus_1.1-4.md
$ :export 彼前3:13-16
$ → studies/1pet_3.13-16.md
$ Current studies directory: {studies_dir}
Packaged defaults are ~/Library/Application Support/scriexe/studies on macOS, ${XDG_DATA_HOME:-~/.local/share}/scriexe/studies on Linux, and %LOCALAPPDATA%\\scriexe\\studies on Windows.
The first export uses <slug>.md. If that path already exists, the next export uses <slug>.notes.md; later exports of the same reference replace that .notes.md file. Export does not modify the original note files.

# More commands and settings
$ :set
Open the Settings page.
$ :set highlight auto|color|minimal
Choose automatic color detection, forced color, or minimal/no-color emphasis. Persisted.
$ :set editor inline|popup
Choose the inline note pane or IME-safe popup editor. Persisted.
$ :set window N
Set the window radius from 1 to 40 verses. Values outside that range are clamped. Persisted.
$ :set notemark <char>
Choose the marker shown beside verses with notes. Up to two characters are stored. Persisted.
$ :setup
Reopen first-run setup for language, translations, downloads, and optional API keys.
$ :help
Open this Help page and reset it to the top.
$ :q
Quit scriexe from the command prompt. Unlike the plain q key, this command does not act as contextual Back.

# Leaving modes
Esc normally returns one level: it closes NAV, Word, Results, Settings, or Help; in active preview find it clears find; in the inline note editor it saves first. The plain q key closes NAV, Settings, Word, Results, or Help, but exits scriexe from normal reading mode.
""",
    "zh": """\
exeg TUI — 快捷键
 导航   Tab 开关导航 · j/k 移动 · l 下钻 · h 返回 · Enter 选定 · Esc 退出
 经文   j/k 上/下一节 · z 阅读范围 · +/- 窗口 · b 返回书签 · p 设置书签
 词汇   （词汇视图）j/k 选择出现位置 · Enter 跳转 · Esc 返回
 笔记   i 编辑笔记（Esc 保存）· :set editor popup 启用输入法友好编辑
 查找   / 查找经文预览 · j/k 下一个/上一个 · Enter 确认 · Esc 清除
 命令   :passage <经文> · :versions <列表> · :scope window|chapter|verse
        :word <查询> · :search <正则> · :export <经文> · :set … · :help · :q

# 详细帮助
本手册说明每种模式和命令实际会改变什么。使用 j/k、方向键、Enter、Ctrl-D 或 Ctrl-U 滚动；按 q 或 Esc 关闭帮助。

# 导航器
按 Tab 打开四列导航器：书卷、章节、经节和词汇。移动选项会立即更新右侧预览，但只有按 Enter 后才会改变正式阅读位置。
$ j / k 或 上 / 下方向键    在当前列移动
$ l / 右方向键             进入下一列
$ h / 左方向键             返回上一列
$ g / G                    跳到当前列第一项 / 最后一项
$ Enter                    打开所选经节或词汇
$ Esc 或 q                 关闭导航，回到已选定的阅读位置
词汇列需要可选的 SBLGNT 或 WLC 原文数据；Strong's 数据会补充词汇资料。如果该列为空，请在首次设置或设置页下载研经资料。

# 阅读范围
阅读范围决定焦点经节周围显示多少上下文。按 z 在三种模式之间循环。
$ window   显示焦点前后的经节；使用 + 和 - 调整范围
$ chapter  显示完整章节
$ verse    只显示焦点经节及其笔记区域
在经文模式中，j/k 移动焦点经节；g/G 跳到当前研读选段的第一节/最后一节；Ctrl-D 与 Ctrl-U 滚动半屏但不改变焦点。
WLC 希伯来文经文正文的每一行都会对齐窗格右边缘；译本标签和其他译本仍保持左对齐。

# 原文词汇研究
在导航器中进入“词汇”列，对希腊文或希伯来文词形按 Enter。词汇视图会显示该词在经文中的位置、lemma、Strong's 信息、词形分析，以及已安装语料中的出现位置。
$ j / k       选择一个出现位置
$ Enter       打开该出现位置所在的经节
$ Esc 或 h    返回经文视图
也可以使用 :word 直接打开查询结果。此功能需要先安装原文与 Strong's 数据。

# 笔记
关闭导航器，把焦点放在一节经文上，然后按 i 编辑该节笔记。在词汇视图按 i，则编辑绑定到该词汇出现位置的笔记。
$ Esc          保存并退出内嵌编辑器
$ Ctrl-C       放弃本次编辑
$ 方向键       移动内嵌编辑器光标
笔记以本地 Markdown 文件保存。已有笔记的经节旁会显示铅笔标记。
中文输入法较多时，可使用 :set editor popup。弹出编辑器使用普通终端输入；Ctrl-D 完成，Ctrl-C 取消；空白提交会保留原笔记。

# 当前预览内查找
在普通经文视图且导航器关闭时，按 / 查找当前已渲染的译本和可见笔记。这是忽略大小写的字面查找，不是正则表达式；它绝不会搜索旧结果、帮助、设置、词汇或导航内容。
$ j / 下方向键    下一个匹配
$ k / 上方向键    上一个匹配
$ Enter            接受当前滚动位置并清除高亮
$ Esc              清除查找，恢复普通经节导航
提交空内容也会清除查找。

# 语料库搜索
:search 使用正则表达式搜索当前已启用且安装在本地的译本。每条结果都会标明来源，例如 [ASV] 或 [CUVS]；它比只查找当前经文预览的 / 范围更广。
$ :search hope
$ :search faith|hope
在结果中使用 j/k 移动可见选项，Enter 打开所选经节，Esc 或 h 返回搜索前的经节。

# 书签
在经文视图按 p 保存当前位置。系统只有一个书签，再次按 p 会替换原书签。按 b 返回书签，同时关闭导航器。书签存在时，标题栏会显示 bm:<经文位置>。
在跟随词汇出现位置或跳到另一段经文之前设置书签，可以快速回到原处。书签只保留到本次程序退出。

# 设置
在经文视图按 o，或输入不带参数的 :set，打开设置。使用 j/k 移动，Enter 或空格切换，Esc 返回。
设置页管理界面语言、可见译本、API Key、笔记标记、可选研经资料和恢复默认值。译本与显示选项会保存到本地。
“下载全部可选研经数据”会安装 SBLGNT、WLC、Strong's、WEB、KJV 和 Vulgate。下载中断时已经完成的数据会保留；再次执行即可重试。

# 命令参考
在导航、经文、词汇、结果或设置模式中，按 : 打开命令输入。输入框打开后，下面示例中的开头冒号可以省略。输入框保留在 TUI 内，并记录本次会话的历史命令。
$ 上 / 下方向键          上一条 / 下一条命令
$ 左 / 右方向键          移动光标
$ Home / Ctrl-A          跳到行首
$ End / Ctrl-E           跳到行尾
$ Backspace / Delete     删除光标前 / 光标处字符
$ Ctrl-U / Ctrl-K        删除行首至光标 / 光标至行尾
$ Enter                  执行
$ Esc / Ctrl-C           取消

$ :passage <经文范围>
建立临时研读选段，并跳到其中第一节。支持英文或中文经文格式。不带参数执行 :passage 会清除选段，并恢复当前章节导航。
$ 示例：:passage Titus 1:1-4
$ 示例：:passage 彼前3:13-16

$ :versions <逗号分隔列表>
在当前会话中明确指定译本。可用 id 包括 cuvs、asv、web、kjv、vulgate、sblgnt、wlc、esv 和 nasb95。该命令会覆盖原文自动选择，但不会替换设置页中持久保存的译本列表。
$ 示例：:versions cuvs,asv
不带列表执行 :versions 会显示当前实际使用的译本。

$ :scope window|chapter|verse
直接设置阅读范围，无需按 z 循环。该选择属于当前会话状态。
$ 示例：:scope chapter

$ :word <Strong's 编号或 lemma>
查询已安装的原文资料并打开出现位置列表。
$ 示例：:word G3958
如果尚未安装研经资料或没有匹配项，状态栏会提示未找到出现位置。

$ :search <正则表达式>
使用正则表达式搜索当前已启用且安装在本地的译本，并打开结果列表。如果只想查找当前预览中的字面文字，请使用 /。
$ 示例：:search hope

# 导出
:export 会把所选经文、当前实际使用的译本，以及关联的书卷/章节/经节/词汇笔记编译为 Markdown。每次导出后，状态栏都会显示文件的完整绝对路径。
$ :export Titus 1:1-4
$ → studies/titus_1.1-4.md
$ :export 彼前3:13-16
$ → studies/1pet_3.13-16.md
$ 当前 studies 目录：{studies_dir}
安装版默认位置：macOS 为 ~/Library/Application Support/scriexe/studies；Linux 为 ${XDG_DATA_HOME:-~/.local/share}/scriexe/studies；Windows 为 %LOCALAPPDATA%\\scriexe\\studies。
首次导出使用 <slug>.md；如果该路径已存在，下一次使用 <slug>.notes.md；之后再次导出同一范围会覆盖该 .notes.md 文件。导出不会修改原始笔记文件。

# 其他命令与设置
$ :set
打开设置页。
$ :set highlight auto|color|minimal
选择自动检测颜色、强制彩色或最简/无彩色强调。会持久保存。
$ :set editor inline|popup
选择内嵌笔记区或输入法友好的弹出编辑器。会持久保存。
$ :set window N
设置 window 模式前后范围，允许 1 至 40；超出范围会自动限制。会持久保存。
$ :set notemark <字符>
设置有笔记经节旁的标记，最多保存两个字符。会持久保存。
$ :setup
重新打开首次设置，调整语言、译本、下载资料和可选 API Key。
$ :help
打开本帮助页，并回到顶部。
$ :q
从命令输入框退出 scriexe。与不带冒号的 q 键不同，这条命令不会按上下文执行“返回”。

# 退出各模式
Esc 通常返回上一层：关闭导航、词汇、结果、设置或帮助；在预览查找中清除查找；在内嵌笔记编辑器中先保存。不带冒号的 q 会关闭导航、设置、词汇、结果或帮助，但在普通经文模式中退出 scriexe。
""",
}


def help_lines(lang: str) -> list[tuple[str, str]]:
    """Return localized, styled lines for the scrollable Help overlay."""
    raw = HELP_MANUAL.get(lang, HELP_MANUAL["en"])
    raw = raw.replace("{studies_dir}", str(corpus.studies_dir().resolve()))
    out: list[tuple[str, str]] = []
    for i, line in enumerate(raw.splitlines()):
        if line.startswith("# "):
            out.append((line[2:], KIND_COLHDR))
        elif line.startswith("$ "):
            out.append(("  " + line[2:], KIND_LABEL))
        elif not line:
            out.append(("", KIND_NORMAL))
        else:
            out.append((line, KIND_HEADER if i == 0 else KIND_NORMAL))
    return out


# --------------------------------------------------------------------------- #
# curses driver
# --------------------------------------------------------------------------- #

def _terminfo_available(name: str) -> bool:
    try:
        return subprocess.run(["infocmp", name], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, check=False).returncode == 0
    except OSError:
        return False


def _direct_term_name(term: str, colorterm: str, available=_terminfo_available) -> str | None:
    if colorterm.lower() not in ("truecolor", "24bit"):
        return None
    candidate = {"tmux-256color": "tmux-direct",
                 "xterm-256color": "xterm-direct"}.get(term)
    return candidate if candidate and available(candidate) else None


def _focus_pair_colors() -> tuple[int, int]:
    colors = getattr(curses, "COLORS", 0)
    if colors >= 1 << 24:
        return 0xFFFFAF, 0x005477
    if colors >= 256:
        return 229, 24
    return curses.COLOR_YELLOW, curses.COLOR_BLUE


class Screen:
    def __init__(self):
        self.stdscr = None
        self.has_color = False
        self._term_prepared = False
        self._original_term: str | None = None
        self._term_changed = False

    def _prepare_term(self):
        if self._term_prepared:
            return
        self._term_prepared = True
        self._original_term = os.environ.get("TERM")
        direct = _direct_term_name(self._original_term or "",
                                   os.environ.get("COLORTERM", ""))
        if direct:
            os.environ["TERM"] = direct
            self._term_changed = True

    def _restore_term_env(self):
        if not self._term_changed:
            return
        if self._original_term is None:
            os.environ.pop("TERM", None)
        else:
            os.environ["TERM"] = self._original_term
        self._term_changed = False

    def open(self):
        self._prepare_term()
        # ncurses otherwise waits about one second to distinguish a standalone
        # Escape press from the start of an arrow/function-key sequence.
        try:
            curses.set_escdelay(25)
        except (AttributeError, curses.error):
            pass
        try:
            self.stdscr = curses.initscr()
        except Exception:
            if not self._term_changed:
                raise
            self._restore_term_env()
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
                focus_fg, focus_bg = _focus_pair_colors()
                curses.init_pair(1, focus_fg, focus_bg)
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
        finally:
            self._restore_term_env()


def _color_on(c: Controller, screen: Screen) -> bool:
    if c.highlight == "minimal":
        return False
    if c.highlight == "color":
        return True
    return screen.has_color


def _attr(kind: str, color: bool) -> int:
    if kind.startswith(RTL_PREFIX):
        kind = kind[len(RTL_PREFIX):]
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
    if kind.startswith(RTL_PREFIX):
        kind = kind[len(RTL_PREFIX):]
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
            find_active = (controller.find_allowed() and controller.find_hits
                           and controller.find_idx >= 0)
            if find_active:
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
                pane_focus = (controller.find_hits[controller.find_idx]
                              if find_active else
                              (-1 if controller.suppress_focus_once else focus_line))
                scroll = _draw_pane(screen, controller, lines, pane_focus, top,
                                    body_h, 0, w, scroll, color)
                controller.suppress_focus_once = False
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
    if c.show_help:
        return (" HELP · j/k/↑/↓ scroll · q/Esc close " if c.lang == "en" else
                " 帮助 · j/k/↑/↓ 滚动 · q/Esc 关闭 ")
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


def _wrap_rtl_version(text: str, width: int) -> list[str]:
    """Keep the version label left while aligning Hebrew body rows right."""
    width = max(1, width)
    match = re.match(r"^(  \S+ {2,})(\S.*)$", text)
    if match:
        prefix, body = match.groups()
        prefix_width = _cell_width(prefix)
        if prefix_width < width:
            body_width = width - prefix_width
            chunks = _wrap_plain(body, body_width)
            return [prefix + " " * max(0, body_width - _cell_width(chunk)) + chunk
                    for chunk in chunks]
    chunks = _wrap_plain(text, width)
    return [" " * max(0, width - _cell_width(chunk)) + chunk for chunk in chunks]


def _build_rows(lines, avail, color, wrap=True):
    """Turn logical lines into display rows, word-wrapping each to `avail`.
    Returns (rows, line_row) where line_row[i] is the starting row of line i."""
    rows = []
    line_row = []
    for text, kind in lines:
        line_row.append(len(rows))
        base_kind = kind[len(RTL_PREFIX):] if kind.startswith(RTL_PREFIX) else kind
        marker = _marker(kind) if (not color and base_kind == KIND_FOCUS) else ""
        content_width = max(1, avail - _cell_width(marker))
        if kind.startswith(RTL_PREFIX) and wrap:
            chunks = _wrap_rtl_version(text, content_width)
        elif wrap and _cell_width(text) + _cell_width(marker) > avail:
            chunks = _wrap_one(text, max(4, content_width))
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


def _prompt_line(screen: Screen, prefix: str, history: list[str]) -> str | None:
    """Edit one line on the status row without leaving curses."""
    editor = LineEditor("", history)
    win = screen.stdscr
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    while True:
        h, w = win.getmaxyx()
        start = 0
        while (start < editor.cursor and
               _cell_width(prefix + ("…" if start else "")
                           + editor.text[start:editor.cursor]) >= max(1, w - 1)):
            start += 1
        lead = prefix + ("…" if start else "")
        visible = lead + editor.text[start:]
        try:
            win.move(h - 1, 0)
            win.clrtoeol()
        except curses.error:
            pass
        _put(win, h - 1, 0, visible, _attr(KIND_STATUS, screen.has_color), w)
        cursor_x = min(max(0, w - 2), _cell_width(lead + editor.text[start:editor.cursor]))
        try:
            win.move(h - 1, cursor_x)
            win.refresh()
            key = win.get_wch()
        except KeyboardInterrupt:
            key = 3
        action = editor.handle(key)
        if action:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            return editor.text if action == "submit" else None


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
        line = _prompt_line(screen, ":", c.command_history)
        if line is not None:
            msg = c.execute(line)
            if msg:
                c.message = msg
        return 0
    if k == ord("/"):
        if not c.find_allowed():
            c.message = ("find is available only in verse view" if c.lang == "en" else
                         "查找仅可用于经文视图")
            return 0
        pat = _prompt_line(screen, "/", c.find_history)
        if pat is not None:
            n = c.find(pat)
            c.message = f"/{pat}: {n} hits" if pat else "find cleared"
            c.find_target_line = c.find_hits[c.find_idx] if c.find_hits else None
        return 0
    if c.find_pat and c.find_allowed():
        if k in (ord("j"), curses.KEY_DOWN):
            c.find_target_line = c.find_next(1)
            return 0
        if k in (ord("k"), curses.KEY_UP):
            c.find_target_line = c.find_next(-1)
            return 0
        if k in (10, 13, curses.KEY_ENTER):
            c.clear_find(suppress_focus=True)
            return 0
        if k == 27:
            c.clear_find()
            return 0
    if k in (9,):  # Tab
        c.toggle_nav()
        return 0
    if k == 63 or (hasattr(curses, "KEY_F0") and k == curses.KEY_F0 + 1):  # "?" or F1
        if not c.show_help:
            c.clear_find()
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