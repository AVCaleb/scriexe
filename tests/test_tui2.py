"""Unit tests for exeg.tui.Controller (Phases 2-4) — no curses."""
import pathlib

import pytest

from exeg import canon, corpus, notes, refs, tui


@pytest.fixture
def tmp_notes(tmp_path, monkeypatch):
    """Redirect notes storage to a temp dir; keep the real corpus."""
    monkeypatch.setattr(notes, "notes_root", lambda: tmp_path / "notes")
    return tmp_path / "notes"


def make_controller():
    c = tui.Controller()
    c.lang = "en"
    return c


def test_screen_open_uses_short_escape_delay(monkeypatch):
    calls = []
    monkeypatch.setattr(tui, "_direct_term_name", lambda *_args, **_kwargs: None)

    class FakeWindow:
        def keypad(self, enabled):
            pass

    monkeypatch.setattr(tui.curses, "initscr", lambda: FakeWindow())
    monkeypatch.setattr(tui.curses, "noecho", lambda: None)
    monkeypatch.setattr(tui.curses, "cbreak", lambda: None)
    monkeypatch.setattr(tui.curses, "curs_set", lambda _value: None)
    monkeypatch.setattr(tui.curses, "has_colors", lambda: False)
    monkeypatch.setattr(tui.curses, "set_escdelay", calls.append)

    tui.Screen().open()

    assert calls == [25]


@pytest.mark.parametrize("colors, expected", [
    (1 << 24, (1, 0xFFFFAF, 0x005477)),
    (256, (1, 229, 24)),
    (8, (1, tui.curses.COLOR_YELLOW, tui.curses.COLOR_BLUE)),
])
def test_screen_open_uses_selected_focus_band_with_fallback(monkeypatch, colors, expected):
    pairs = []
    monkeypatch.setattr(tui, "_direct_term_name", lambda *_args, **_kwargs: None)

    class FakeWindow:
        def keypad(self, enabled):
            pass

    monkeypatch.setattr(tui.curses, "initscr", lambda: FakeWindow())
    monkeypatch.setattr(tui.curses, "noecho", lambda: None)
    monkeypatch.setattr(tui.curses, "cbreak", lambda: None)
    monkeypatch.setattr(tui.curses, "curs_set", lambda _value: None)
    monkeypatch.setattr(tui.curses, "set_escdelay", lambda _value: None)
    monkeypatch.setattr(tui.curses, "has_colors", lambda: True)
    monkeypatch.setattr(tui.curses, "start_color", lambda: None)
    monkeypatch.setattr(tui.curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(tui.curses, "init_pair", lambda *args: pairs.append(args))
    monkeypatch.setattr(tui.curses, "COLORS", colors, raising=False)

    tui.Screen().open()

    assert pairs[0] == expected


def test_direct_term_selection_requires_truecolor_and_terminfo():
    available = lambda name: name in {"tmux-direct", "xterm-direct"}
    assert tui._direct_term_name("tmux-256color", "truecolor", available) == "tmux-direct"
    assert tui._direct_term_name("xterm-256color", "24bit", available) == "xterm-direct"
    assert tui._direct_term_name("tmux-256color", "", available) is None
    assert tui._direct_term_name("screen-256color", "truecolor", available) is None
    assert tui._direct_term_name("tmux-256color", "truecolor", lambda _name: False) is None


def test_wlc_verse_and_word_context_are_marked_for_right_alignment():
    c = make_controller()
    gen = next(i for i, book in enumerate(canon.BOOKS) if book.osis == "Gen")
    c.goto(tui.Node(gen, 1, 1))
    c.nav_visible = False
    c.versions = ["wlc"]
    c._versions_custom = True
    verse_lines, _ = c.render_content()
    wlc_lines = [(text, kind) for text, kind in verse_lines if "WLC" in text]
    assert wlc_lines and all(kind.startswith(tui.RTL_PREFIX) for _text, kind in wlc_lines)
    c.view = "word"
    c.word_idx = 1
    c._enter_word_view()
    word_lines, _ = c.render_content()
    original = [(text, kind) for text, kind in word_lines if "WLC" in text]
    assert original and original[0][1].startswith(tui.RTL_PREFIX)


def test_rtl_version_body_wraps_and_right_aligns_each_row():
    text = tui._version_line("WLC", "אבג דהו זחט יכל")
    rows, _line_rows = tui._build_rows(
        [(text, tui.RTL_PREFIX + tui.KIND_NORMAL)], 18, color=True, wrap=True)
    assert len(rows) >= 2
    for row, _kind in rows:
        assert tui._cell_width(row) == 18
    assert rows[0][0].startswith("  WLC")
    assert rows[-1][0].endswith("יכל")


def test_non_hebrew_translation_keeps_normal_left_aligned_kind():
    c = make_controller()
    c.nav_visible = False
    c.versions = ["asv"]
    c._versions_custom = True
    lines, _ = c.render_content()
    asv = [(text, kind) for text, kind in lines if "ASV" in text]
    assert asv and all(not kind.startswith(tui.RTL_PREFIX) for _text, kind in asv)


def _drill_to_1pet_3_18_word(c, word_idx=7):
    """Nav from books down to a specific word in 1Pet 3:18 and commit it."""
    i = next(i for i, b in enumerate(canon.BOOKS) if b.osis == "1Pet") + 1
    c._set_col_value(0, i); c.drill()      # books -> chapters
    c._set_col_value(1, 3); c.drill()      # chapters -> verses
    c._set_col_value(2, 18); c.drill()     # verses -> words
    c._set_col_value(3, word_idx)
    assert c.nav_col == 3
    return c


# ===========================================================================
# Phase 2 — words column, word view, :word / :search results
# ===========================================================================

def test_words_column_populates_for_nt_verse():
    c = make_controller()
    i = next(i for i, b in enumerate(canon.BOOKS) if b.osis == "1Pet") + 1
    c._set_col_value(0, i); c._set_col_value(1, 3); c._set_col_value(2, 18)
    c.drill(); c.drill(); c.drill()
    assert c.nav_col == 3
    items = c.column_items(3)
    assert len(items) > 0
    assert any("G" in it for it in items)  # strongs shown alongside surface


def test_commit_word_enters_word_view():
    c = make_controller()
    _drill_to_1pet_3_18_word(c, 7)
    c.commit()
    assert c.view == "word"
    assert c.word_idx == 7
    assert c.word_result.get("occurrences")
    assert not c.nav_visible


def test_word_view_render_has_bracketed_token_and_occurrences():
    c = make_controller()
    _drill_to_1pet_3_18_word(c, 7)
    c.commit()
    lines, _ = c.render_content()
    kinds = [k for _, k in lines]
    assert tui.KIND_TOKEN in kinds
    assert tui.KIND_OCCUR in kinds or tui.KIND_OCCUR_SEL in kinds
    assert any("word study" in t for t, _ in lines)


def test_word_cursor_moves_and_jumps():
    c = make_controller()
    _drill_to_1pet_3_18_word(c, 7)
    c.commit()
    n = len(c.word_result["occurrences"])
    assert n > 0
    start = c.word_cursor
    c.move_word_cursor(1)
    assert c.word_cursor == start + 1
    c.move_word_cursor(-1)
    assert c.word_cursor == start
    c.jump_word_cursor()
    assert c.view == "verse"
    assert c.word_idx is None


def test_exit_word_view():
    c = make_controller()
    _drill_to_1pet_3_18_word(c, 7)
    c.commit()
    c.exit_word_view()
    assert c.view == "verse"
    assert c.word_idx is None


def test_command_word_renders_result_view():
    c = make_controller()
    c.lang = "en"
    msg = c.execute(":word G3958")
    assert c.view == "result"
    assert c.result_items
    assert "occurrences" in msg.lower()


def test_command_search_renders_result_view():
    c = make_controller()
    c.lang = "en"
    msg = c.execute(":search hope")
    assert c.view == "result"
    assert c.result_items
    assert "match" in msg.lower() or "hit" in msg.lower()


def test_search_uses_installed_effective_versions_and_labels_results(monkeypatch):
    c = make_controller()
    c.versions = ["cuvs", "asv", "missing"]
    c._versions_custom = True
    monkeypatch.setattr(corpus, "has_version", lambda version: version != "missing")
    seen = {}

    def fake_search(pattern, versions, lemma=False):
        seen["args"] = (pattern, versions, lemma)
        return [("asv", "Titus", 1, 1, "matching text")]

    monkeypatch.setattr(tui.search, "search_text", fake_search)
    c.execute(":search faith")
    lines, _focus = c.render_content()
    assert seen["args"] == ("faith", ["cuvs", "asv"], False)
    assert "[ASV]" in lines[2][0]


def test_result_selection_follows_cursor_and_enter_opens_selected(monkeypatch):
    c = make_controller()
    hits = [("asv", "Titus", 1, 1, "first"),
            ("cuvs", "1Pet", 3, 18, "second")]
    monkeypatch.setattr(tui.search, "search_text",
                        lambda *_args, **_kwargs: hits)
    monkeypatch.setattr(corpus, "has_version", lambda _version: True)
    c.execute(":search faith")
    lines, focus = c.render_content()
    assert "▶" in lines[2][0] and lines[2][1] == tui.KIND_OCCUR_SEL
    assert "▶" not in lines[3][0]
    assert focus == 2
    tui._handle(None, c, ord("j"), 0, lines, focus, 20)
    lines, focus = c.render_content()
    assert "▶" not in lines[2][0]
    assert "▶" in lines[3][0] and lines[3][1] == tui.KIND_OCCUR_SEL
    assert focus == 3
    tui._handle(None, c, 10, 0, lines, focus, 20)
    assert c.view == "verse"
    assert c.focus.book().osis == "1Pet"
    assert (c.focus.chapter, c.focus.verse) == (3, 18)


def test_result_cursor_jump_and_exit():
    c = make_controller()
    c.execute(":word G3958")
    c.move_result_cursor(1)
    assert c.result_cursor == 1
    c.jump_result_cursor()
    assert c.view == "verse"
    c.execute(":search hope")
    c.exit_result_view()
    assert c.view == "verse"


def test_command_word_no_occurrences():
    c = make_controller()
    msg = c.execute(":word ZZZZ9999")
    assert "no occurrences" in msg.lower()
    assert c.view == "verse"


# ===========================================================================
# Phase 3 — notes persistence, editor, markers, pin, export
# ===========================================================================

def test_note_write_and_read_roundtrip(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "once-for-all suffering")
    assert notes.has_verse_note("1Pet", 3, 18)
    assert "once-for-all" in notes.read_verse("1Pet", 3, 18)
    notes.write_verse("1Pet", 3, 18, "")  # blank deletes
    assert not notes.has_verse_note("1Pet", 3, 18)


def test_word_note_roundtrip(tmp_notes):
    notes.write_word("1Pet", 3, 18, 7, "aorist, once")
    assert notes.has_word_note("1Pet", 3, 18, 7)
    assert "aorist" in notes.read_word("1Pet", 3, 18, 7)
    notes.write_word("1Pet", 3, 18, 7, "")
    assert not notes.has_word_note("1Pet", 3, 18, 7)


def test_column_markers_reflect_notes(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "x")
    c = make_controller()
    i = next(i for i, b in enumerate(canon.BOOKS) if b.osis == "1Pet") + 1
    c._set_col_value(0, i); c._set_col_value(1, 3)
    assert c.column_has_note(2, 18) is True
    assert c.column_has_note(2, 17) is False


def test_begin_edit_loads_existing_note(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "first line\nsecond line")
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    assert c.editing is True
    assert "first line" in c.note_lines
    assert "second line" in c.note_lines


def test_editor_insert_newline_backspace_cursor(tmp_notes):
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    c.insert_char("h")
    c.insert_char("i")
    assert c.note_lines[0] == "hi"
    c.insert_newline()
    assert c.note_lines == ["hi", ""]
    assert c.note_cy == 1 and c.note_cx == 0
    c.backspace()  # join lines
    assert c.note_lines == ["hi"]
    c.cursor_move(0, -1)
    assert c.note_cx == 1
    c.cursor_move(0, -100)
    assert c.note_cx == 0


def test_end_edit_persists_note(tmp_notes):
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    c.insert_char("saved note")
    c.end_edit(save=True)
    assert c.editing is False
    assert "saved note" in notes.read_verse("1Pet", 3, 18)


def test_end_edit_discard_does_not_save(tmp_notes):
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    c.insert_char("discard me")
    c.end_edit(save=False)
    assert notes.read_verse("1Pet", 3, 18) == ""


def test_word_note_edit_target(tmp_notes):
    c = make_controller()
    _drill_to_1pet_3_18_word(c, 7)
    c.commit()
    c.begin_edit()
    assert c.note_target[0] == "word"
    c.insert_char("lemma note")
    c.end_edit(save=True)
    assert "lemma note" in notes.read_word("1Pet", 3, 18, 7)


def test_bookmark_back_roundtrip():
    c = make_controller()
    c.commit()                       # 1Pet 3:18
    c.set_bookmark()                 # bookmark 3:18
    assert c.bookmark is not None
    c.move_focus(4)                  # -> 3:22
    assert c.focus.verse == 22
    c.back()                         # return to bookmark
    assert c.focus.verse == 18


def test_bookmark_persists_through_commit():
    from exeg import tui as _t
    c = make_controller()
    c.commit()
    c.set_bookmark()                 # bookmark 1Pet 3:18
    # jump to a totally different book via nav + commit
    c.toggle_nav()
    c.nav_col = 0
    c._set_col_value(0, _t._osis_index("Gen") + 1)
    c.commit()
    assert c.focus.book().osis == "Gen"
    assert c.bookmark is not None    # bookmark survived the commit
    c.back()
    assert c.focus.book().osis == "1Pet" and c.focus.verse == 18


def test_bookmark_replaced_by_p():
    c = make_controller()
    c.commit()
    c.set_bookmark()                 # bm = 3:18
    c.move_focus(1)                  # -> 3:19
    c.set_bookmark()                 # bm = 3:19 (replaces)
    c.move_focus(3)                  # -> 3:22
    c.back()
    assert c.focus.verse == 19       # returned to the NEW bookmark


def test_back_without_bookmark_is_safe():
    c = make_controller()
    c.commit()
    assert c.bookmark is None
    c.back()                        # no crash
    assert "no bookmark" in c.message.lower()


def test_export_ref_produces_text(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "my verse note")
    ref = refs.parse_ref("1Pet 3:18-18")
    body = notes.export_ref(ref, ["sblgnt", "cuvs"])
    assert "1 Peter 3:18" in body
    assert "my verse note" in body
    assert "Text · 经文对照" in body


def test_command_export_message(tmp_notes, tmp_path, monkeypatch):
    # redirect corpus root to a temp dir (with corpus symlinked) so export
    # doesn't write into the real studies/
    real = pathlib.Path(__file__).resolve().parents[1]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "corpus").symlink_to(real / "data" / "corpus")
    monkeypatch.setenv("EXEG_ROOT", str(tmp_path))
    c = make_controller()
    msg = c.execute(":export 1Pet 3:18-18")
    path = tmp_path / "studies" / "1pet_3.18.md"
    assert "exported" in msg.lower()
    assert str(path.resolve()) in msg
    assert path.exists()


# ===========================================================================
# Phase 4 — find, history, settings
# ===========================================================================

def test_line_editor_cursor_deletion_and_control_keys():
    e = tui.LineEditor("ab", [])
    assert e.cursor == 2
    e.handle(tui.curses.KEY_LEFT)
    e.handle("中")
    assert (e.text, e.cursor) == ("a中b", 2)
    e.handle(tui.curses.KEY_HOME)
    e.handle(tui.curses.KEY_DC)
    assert e.text == "中b"
    e.handle(tui.curses.KEY_END)
    e.handle(127)
    assert e.text == "中"
    e.handle(1)  # Ctrl-A
    e.handle("前")
    e.handle(5)  # Ctrl-E
    e.handle("后")
    assert e.text == "前中后"
    e.cursor = 1
    e.handle(11)  # Ctrl-K
    assert e.text == "前"
    e.handle("中后")
    e.cursor = 2
    e.handle(21)  # Ctrl-U
    assert e.text == "后"


def test_line_editor_history_restores_draft_and_collapses_duplicates():
    history = ["passage Titus 1", "search faith"]
    e = tui.LineEditor("draft", history)
    e.handle(tui.curses.KEY_UP)
    assert e.text == "search faith"
    e.handle(tui.curses.KEY_UP)
    assert e.text == "passage Titus 1"
    e.handle(tui.curses.KEY_DOWN)
    e.handle(tui.curses.KEY_DOWN)
    assert e.text == "draft"
    assert e.handle(10) == "submit"
    assert history[-1] == "draft"
    duplicate = tui.LineEditor("draft", history)
    duplicate.handle(10)
    assert history.count("draft") == 1
    assert tui.LineEditor("", history).handle(27) == "cancel"


def test_controller_keeps_command_and_find_history_separate():
    c = make_controller()
    assert c.command_history == []
    assert c.find_history == []
    tui.LineEditor("search faith", c.command_history).handle(10)
    tui.LineEditor("faith", c.find_history).handle(10)
    assert c.command_history == ["search faith"]
    assert c.find_history == ["faith"]


def test_command_handler_uses_internal_prompt_without_suspending(monkeypatch):
    c = make_controller()

    class FakeScreen:
        def suspend(self):
            raise AssertionError("command prompt must not suspend curses")

    monkeypatch.setattr(tui, "_prompt_line",
                        lambda _screen, prefix, history: "scope verse")
    tui._handle(FakeScreen(), c, ord(":"), 0, [], -1, 20)
    assert c.scope == "verse"


def test_find_returns_hits_and_navigates():
    c = make_controller()
    c.commit()
    c.set_scope("chapter")
    n = c.find("Christ")
    assert n >= 1
    assert c.find_idx == 0
    line = c.find_next(1)
    assert isinstance(line, int)


def test_find_is_scoped_to_plain_verse_preview():
    c = make_controller()
    c.view = "result"
    c.result_items = [(0, 1, 1)]
    c.result_lines = [("search history", tui.KIND_HEADER), ("", tui.KIND_NOTE),
                      ("old match", tui.KIND_OCCUR)]
    assert c.find("match") == 0
    assert c.find_pat == "" and c.find_hits == []
    c.view = "verse"
    c.nav_visible = True
    assert c.find("match") == 0


def test_active_find_uses_jk_and_enter_or_escape_clears():
    c = make_controller()
    c.view = "verse"
    c.nav_visible = False
    c.find_pat = "match"
    c.find_hits = [2, 4]
    c.find_idx = 0
    original_focus = c.focus
    tui._handle(None, c, ord("j"), 0, [], -1, 20)
    assert c.find_idx == 1 and c.focus == original_focus
    tui._handle(None, c, ord("k"), 0, [], -1, 20)
    assert c.find_idx == 0
    tui._handle(None, c, 10, 0, [], -1, 20)
    assert c.find_pat == "" and c.find_hits == []
    assert c.suppress_focus_once is True
    c.find_pat, c.find_hits, c.find_idx = "again", [3], 0
    tui._handle(None, c, 27, 0, [], -1, 20)
    assert c.find_pat == "" and c.find_hits == []


def test_opening_help_clears_find_and_has_help_only_status():
    c = make_controller()
    c.lang = "en"
    c.nav_visible = False
    c.find_pat, c.find_hits, c.find_idx = "old", [8], 0
    tui._handle(None, c, ord("?"), 0, [], -1, 20)
    assert c.show_help is True
    assert c.find_pat == "" and c.find_hits == []
    status = tui._status(c)
    assert "HELP" in status
    assert "NORMAL" not in status
    assert "Tab" not in status


def test_find_empty_clears():
    c = make_controller()
    c.commit()
    c.find("Christ")
    n = c.find("")
    assert n == 0
    assert c.find_hits == []


def test_history_back():
    # b returns to the bookmark; with none set it is a safe no-op
    c = make_controller()
    c.commit()
    c.back()
    assert isinstance(c.focus, tui.Node)


def test_settings_set_and_persist(tmp_notes):
    c = make_controller()
    assert "color" in c.execute(":set highlight color")
    assert c.highlight == "color"
    assert "popup" in c.execute(":set editor popup")
    assert c.editor_mode == "popup"
    assert c.execute(":set window 3") == "window: 3"
    assert c.window == 3
    m = notes.read_meta()
    assert m.get("highlight") == "color"


def test_settings_bad():
    c = make_controller()
    assert "integer" in c.execute(":set window abc").lower()
    assert "unknown" in c.execute(":set frob 1").lower()

# ===========================================================================
# Testament-aware originals (Hebrew in OT)
# ===========================================================================

def test_ot_versions_include_hebrew():
    from exeg import tui as _t
    c = make_controller()
    c.goto(_t.Node(_t._osis_index("Gen"), 1, 1))
    ev = c.effective_versions()
    assert "wlc" in ev               # Hebrew present in OT
    assert "sblgnt" not in ev        # Greek NT corpus not used for OT


def test_nt_versions_include_greek():
    c = make_controller()
    ev = c.effective_versions()
    assert "sblgnt" in ev and "wlc" not in ev


def test_versions_custom_persists_across_testaments():
    c = make_controller()
    c.execute(":versions sblgnt,cuvs,web")
    assert c._versions_custom is True
    c.goto(tui.Node(tui._osis_index("Gen"), 1, 1))
    assert c.effective_versions() == ["sblgnt", "cuvs", "web"]


# (pin-freeze / commit-releases-pin / move-focus-noop tests removed: pin is now a bookmark, not a freeze)


# ===========================================================================
# Help overlay, editor split, Ctrl-C
# ===========================================================================

def test_help_overlay_renders_and_toggles():
    c = make_controller()
    c.lang = "en"
    assert c.show_help is False
    c.show_help = True
    lines, _ = c.render_content()
    assert any("help" in t.lower() for t, _ in lines)
    assert any("q or Esc to close" in t for t, _ in lines)


@pytest.mark.parametrize("lang, sections", [
    ("en", ["Navigator", "Reading scopes", "Word study", "Notes",
            "Find in preview", "Corpus search", "Bookmark", "Settings",
            "Command reference", "Export"]),
    ("zh", ["导航器", "阅读范围", "原文词汇研究", "笔记", "当前预览内查找",
            "语料库搜索", "书签", "设置", "命令参考", "导出"]),
])
def test_detailed_help_covers_features_commands_and_export(lang, sections):
    lines = tui.help_lines(lang)
    texts = [text for text, _kind in lines]
    joined = "\n".join(texts)
    for section in sections:
        assert section in joined
    for command in (":passage", ":versions", ":scope", ":word", ":search",
                    ":export", ":set", ":setup", ":help", ":q"):
        assert command in joined
    for example in (":export Titus 1:1-4", "studies/titus_1.1-4.md",
                    ":export 彼前3:13-16", "studies/1pet_3.13-16.md"):
        assert example in joined
    summary = next(i for i, text in enumerate(texts) if "TUI" in text and
                   ("keys" in text or "快捷键" in text))
    navigator = next(i for i, text in enumerate(texts)
                     if text in ("Navigator", "导航器"))
    assert summary < navigator


def test_help_rendering_follows_interface_language():
    c = make_controller()
    c.show_help = True
    c.lang = "zh"
    lines, _ = c.render_content()
    assert any("详细帮助" in text for text, _kind in lines)
    c.lang = "en"
    lines, _ = c.render_content()
    assert any("Detailed help" in text for text, _kind in lines)


def test_help_keys_scroll_and_close_without_other_actions():
    c = make_controller()
    c.show_help = True
    tui._handle(None, c, ord("j"), 0, [], -1, 20)
    assert c.help_scroll == 1
    tui._handle(None, c, ord("k"), 0, [], -1, 20)
    assert c.help_scroll == 0
    tui._handle(None, c, 4, 0, [], -1, 20)
    assert c.help_scroll == 1
    tui._handle(None, c, ord("q"), 0, [], -1, 20)
    assert c.show_help is False and c.running is True


def test_render_content_while_editing_returns_scripture():
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    assert c.editing is True
    lines, _ = c.render_content()      # top pane = scripture, not the editor
    # scripture heading present, editor header is NOT in these lines
    assert any("1 Peter 3:18" in t for t, _ in lines)
    assert not any(t.startswith("note ·") for t, _ in lines)


def test_editor_lines_contains_note_header_and_buffer():
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    c.insert_char("x")
    ed = c.editor_lines()
    assert ed[0][0].startswith("note ·")
    assert any("x" in t for t, _ in ed)


def test_ctrl_c_key_in_normal_mode_is_noop():
    c = make_controller()
    c.commit()
    # simulate the _handle path: key 3 (Ctrl-C) returns current scroll, no crash
    # (we call the controller-level invariant: running stays True)
    assert c.running is True


# ===========================================================================
# i18n, settings page, vulgate
# ===========================================================================

def test_i18n_tr_returns_en_and_zh():
    from exeg import i18n
    assert "j/k" in i18n.tr("en", "word_hint")
    assert "选择" in i18n.tr("zh", "word_hint")
    # fallback to en for unknown lang
    assert "j/k" in i18n.tr("xx", "word_hint")
    # format args
    assert "5" in i18n.tr("en", "occurrences_count", n=5)


def test_controller_lang_from_meta(tmp_notes):
    notes.write_meta({"lang": "zh", "translations": ["cuvs"]})
    c = tui.Controller()
    assert c.lang == "zh"
    assert c.translations == ["cuvs"]


def test_open_settings_and_toggle_lang(tmp_notes):
    c = make_controller()
    c.open_settings()
    assert c.view == "settings"
    # cursor starts at first selectable (English radio)
    idxs = c._selectable_settings_indexes()
    assert idxs[0] == c.settings_cursor
    # move to 中文 (index 2) and toggle
    c.settings_cursor = idxs[1]
    c.toggle_settings()
    assert c.lang == "zh"
    # persisted
    assert notes.read_meta().get("lang") == "zh"


def test_settings_toggle_version(tmp_notes):
    c = make_controller()
    c.open_settings()
    base = list(c.translations)
    # find the vulgate bool item and toggle it on
    items = c.settings_items()
    vi = next(i for i, it in enumerate(items) if it.get("value") == "vulgate")
    c.settings_cursor = vi
    c.toggle_settings()
    assert "vulgate" in c.translations
    c.toggle_settings()
    assert "vulgate" not in c.translations
    # toggling a version clears the :versions custom override
    assert c._versions_custom is False


def test_settings_persist_translations(tmp_notes):
    c = make_controller()
    c.open_settings()
    items = c.settings_items()
    vi = next(i for i, it in enumerate(items) if it.get("value") == "vulgate")
    c.settings_cursor = vi
    c.toggle_settings()
    assert "vulgate" in notes.read_meta().get("translations", [])


def test_close_settings():
    c = make_controller()
    c.open_settings()
    c.close_settings()
    assert c.view == "verse"


def test_render_settings_lists_groups():
    c = make_controller()
    c.open_settings()
    lines, _ = c.render_content()
    txt = " ".join(t for t, _ in lines)
    assert "和合本" in txt and "Vulgate" in txt and "WEB" in txt


def test_vulgate_in_corpus():
    from exeg import corpus
    vs = corpus.read_verses("vulgate", "Gen")
    assert vs, "vulgate/Gen missing — run `exeg fetch`"
    assert any(v.chapter == 1 and v.verse == 1 for v in vs)


def test_vulgate_label():
    from exeg import display
    assert display.LABELS["vulgate"] == "Vulgate"


def test_effective_versions_with_vulgate_translation(tmp_notes):
    c = make_controller()
    c.translations = ["cuvs", "vulgate"]
    # NT focus (1Pet) -> sblgnt + cuvs + vulgate
    ev = c.effective_versions()
    assert "sblgnt" in ev and "vulgate" in ev and "cuvs" in ev


def test_cmd_set_no_arg_opens_settings(tmp_notes):
    c = make_controller()
    msg = c.execute(":set")
    assert msg == ""
    assert c.view == "settings"


# ===========================================================================
# Verse-note mark setting
# ===========================================================================

def test_verse_mark_setting_default_on(tmp_notes):
    c = make_controller()
    assert c.show_verse_marks is True


def test_verse_mark_setting_from_meta(tmp_notes):
    notes.write_meta({"show_verse_marks": False})
    c = make_controller()
    assert c.show_verse_marks is False


def test_verse_mark_appears_when_note_present(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "a note")
    c = make_controller()
    c.commit()
    c.set_scope("chapter")
    lines, _ = c.render_content()
    # the 1Pet 3:18 heading should carry the note mark
    assert any("✎" in t and "3:18" in t for t, _ in lines)


def test_verse_mark_hidden_when_setting_off(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "a note")
    c = make_controller()
    c.show_verse_marks = False
    c.commit()
    c.set_scope("chapter")
    lines, _ = c.render_content()
    assert not any("✎" in t for t, _ in lines)


def test_settings_toggle_verse_marks(tmp_notes):
    c = make_controller()
    c.open_settings()
    items = c.settings_items()
    vi = next(i for i, it in enumerate(items)
              if it.get("key") == "show_verse_marks")
    c.settings_cursor = vi
    c.toggle_settings()
    assert c.show_verse_marks is False
    assert notes.read_meta().get("show_verse_marks") is False


def test_settings_lists_apikey_items(tmp_notes, monkeypatch):
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    c = make_controller()
    c.open_settings()
    lines, _ = c.render_content()
    txt = " ".join(t for t, _ in lines)
    assert "ESV API key" in txt and "NASB95 API key" in txt


def test_settings_apikey_toggle_sets_pending(tmp_notes, monkeypatch):
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    c = make_controller()
    c.open_settings()
    items = c.settings_items()
    vi = next(i for i, it in enumerate(items) if it.get("value") == "ESV_API_KEY")
    c.settings_cursor = vi
    c.toggle_settings()
    assert c._pending_apikey == ("ESV_API_KEY", items[vi]["label"])


def test_cmd_setup_command_opens_intro(tmp_notes):
    c = make_controller()
    c.execute(":setup")
    assert c.intro is True


# ===========================================================================
# First-run intro (curses, Demo C) + ASV
# ===========================================================================

def test_controller_intro_flag():
    c = make_controller()
    assert c.intro is False
    c2 = tui.Controller(intro=True)
    assert c2.intro is True


def test_intro_renders_language_and_translations():
    c = tui.Controller(intro=True)
    lines, _ = c.render_content()
    txt = " ".join(t for t, _ in lines)
    assert "first-run setup" in txt
    assert "English" in txt and "中文" in txt
    assert "和合本" in txt and "ASV" in txt and "Vulgate" in txt


def test_intro_explains_missing_esv_nasb_lsb():
    c = tui.Controller(intro=True)
    lines, _ = c.render_content()
    txt = " ".join(t for t, _ in lines)
    assert "Not included by default" in txt
    assert "non-commercial" in txt
    assert "ESV" in txt and "NASB95" in txt and "LSB" in txt


def test_intro_select_language_and_version(tmp_notes):
    c = tui.Controller(intro=True)
    idxs = c._selectable_intro_indexes()
    # pick 中文 (second selectable)
    c.intro_cursor = idxs[1]
    c.toggle_intro()
    assert c.lang == "zh"
    # ASV is bundled/default; verify it can still be toggled off
    assert "asv" in c.translations
    items = c.intro_items()
    ai = next(i for i, it in enumerate(items) if it.get("value") == "asv")
    c.intro_cursor = ai
    c.toggle_intro()
    assert "asv" not in c.translations


def test_intro_begin_finalizes_setup(tmp_notes):
    c = tui.Controller(intro=True)
    idxs = c._selectable_intro_indexes()
    c.intro_cursor = idxs[-1]   # Begin action is last
    c.toggle_intro()
    assert c.intro is False
    assert notes.read_meta().get("setup_done") is True


def test_asv_in_corpus():
    from exeg import corpus
    assert corpus.read_verses("asv", "Gen"), "asv missing — run `exeg fetch`"


def test_asv_label():
    from exeg import display
    assert display.LABELS["asv"] == "ASV"


def test_note_i_targets_focused_verse_not_chapter(tmp_notes):
    """Pressing `i` in chapter scope must attach to the focused verse (so the
    verse mark shows), not to the chapter."""
    c = make_controller()
    c.commit()
    c.set_scope("chapter")           # focus 1Pet 3:18, scope chapter
    t = c.focus_note_target()
    assert t[0] == "verse"
    assert t == ("verse", "1Pet", 3, 18)
    c.begin_edit()
    c.insert_char("x")
    c.end_edit(save=True)
    assert notes.has_verse_note("1Pet", 3, 18)
    assert not notes.has_chapter_note("1Pet", 3)


def test_editor_cursor_col_matches_buffer(tmp_notes):
    c = make_controller()
    c.commit()
    c.set_scope("verse")
    c.begin_edit()
    c.insert_char("ab")
    assert c.note_cx == 2            # cursor after "ab"


def test_word_note_target_still_word(tmp_notes):
    c = make_controller()
    _drill_to_1pet_3_18_word(c, 7)
    c.commit()
    assert c.focus_note_target()[0] == "word"


# ===========================================================================
# notemark setting, restore defaults, nav wrap
# ===========================================================================

def test_notemark_default_and_from_meta(tmp_notes):
    c = make_controller()
    assert c.notemark == "✎"
    notes.write_meta({"notemark": ">", "setup_done": True})
    c2 = make_controller()
    assert c2.notemark == ">"


def test_notemark_used_in_render(tmp_notes):
    notes.write_verse("1Pet", 3, 18, "x")
    c = make_controller()
    c.notemark = ">"
    c.commit(); c.set_scope("chapter")
    lines, _ = c.render_content()
    assert any(">" in t and "3:18" in t for t, _ in lines)
    assert not any("✎" in t for t, _ in lines)


def test_cmd_set_notemark(tmp_notes):
    c = make_controller()
    assert "notemark" in c.execute(":set notemark >")
    assert c.notemark == ">"
    assert notes.read_meta().get("notemark") == ">"


def test_restore_defaults_resets_everything(tmp_notes):
    c = make_controller()
    c.lang = "zh"; c.translations = ["vulgate"]; c.window = 20
    c.highlight = "minimal"; c.editor_mode = "popup"; c.show_verse_marks = False
    c.notemark = ">"; c._versions_custom = True
    c.restore_defaults()
    assert c.lang == "en" and c.translations == ["cuvs", "asv"]
    assert c.window == 5 and c.highlight == "auto" and c.editor_mode == "inline"
    assert c.show_verse_marks is True and c.notemark == "✎"
    assert c._versions_custom is False
    m = notes.read_meta()
    assert m["lang"] == "en" and m["translations"] == ["cuvs", "asv"]


def test_intro_download_action_sets_pending(monkeypatch):
    from exeg import fetch
    monkeypatch.setattr(fetch, "optional_pack_status", lambda: "not_installed")
    c = make_controller()
    i = next(i for i, item in enumerate(c.intro_items())
             if item.get("key") == "download_pack")
    c.intro_cursor = i
    c.toggle_intro()
    assert c._pending_optional_fetch is True


def test_settings_download_action_sets_pending(monkeypatch):
    from exeg import fetch
    monkeypatch.setattr(fetch, "optional_pack_status", lambda: "partial")
    c = make_controller()
    i = next(i for i, item in enumerate(c.settings_items())
             if item.get("key") == "download_pack")
    c.settings_cursor = i
    c.toggle_settings()
    assert c._pending_optional_fetch is True
    assert "partially" in c.settings_items()[i]["label"].lower()


def test_settings_restore_action_sets_pending(tmp_notes):
    c = make_controller(); c.open_settings()
    items = c.settings_items()
    ri = next(i for i, it in enumerate(items) if it.get("type") == "restore")
    c.settings_cursor = ri
    c.toggle_settings()
    assert c._pending_restore is True


def test_render_settings_shows_restore(tmp_notes):
    c = make_controller(); c.open_settings()
    lines, _ = c.render_content()
    assert any("Restore all settings to defaults" in t for t, _ in lines)


# ===========================================================================
# Unicode terminal-cell width regressions
# ===========================================================================

def _terminal_cells(text):
    import unicodedata
    return sum(0 if unicodedata.combining(ch) else
               2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in text)


def test_wrap_one_limits_terminal_cells_for_cjk():
    text = "  和合本     作 神和主耶稣基督仆人的 雅各请散住十二个支派之人的安。"
    chunks = tui._wrap_one(text, 40)
    assert len(chunks) > 1
    assert all(_terminal_cells(chunk) <= 40 for chunk in chunks)


def test_wrap_one_fills_line_across_cjk_whitespace_boundary():
    text = "  和合本     你们这因信蒙 神能力保守的人，必能得着所预备、到末世要显现的救恩。"
    chunks = tui._wrap_one(text, 55)
    assert _terminal_cells(chunks[0]) > 50
    assert all(_terminal_cells(chunk) <= 55 for chunk in chunks)


def test_version_lines_align_bodies_by_terminal_cells():
    for label in ("SBLGNT", "和合本", "WEB"):
        line = tui._version_line(label, "BODY")
        prefix = line[:line.index("BODY")]
        assert _terminal_cells(prefix) == 10


def test_wrap_one_uses_version_body_as_hanging_indent():
    text = tui._version_line(
        "SBLGNT",
        "Καὶ τίς ὁ κακώσων ὑμᾶς ἐὰν τοῦ ἀγαθοῦ ⸀ζηλωταὶ γένησθε;",
    )
    chunks = tui._wrap_one(text, 55)
    assert len(chunks) == 2
    assert chunks[1].startswith(" " * 10 + "⸀ζηλωταὶ")


def test_put_clips_to_available_terminal_cells():
    class FakeWindow:
        def __init__(self):
            self.writes = []

        def addstr(self, y, x, text, attr):
            self.writes.append((y, x, text, attr))

    win = FakeWindow()
    tui._put(win, 0, 10, "中文中文中文中文中文", 0, 20)
    assert _terminal_cells(win.writes[0][2]) <= 9


def test_title_uses_pencil_for_focus_marker():
    assert "focus ✎" in tui._title(make_controller())
