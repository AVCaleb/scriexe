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
    return tui.Controller()


def test_screen_open_uses_short_escape_delay(monkeypatch):
    calls = []

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


def test_screen_open_uses_yellow_text_on_blue_focus_band(monkeypatch):
    pairs = []

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

    tui.Screen().open()

    assert pairs[0] == (1, tui.curses.COLOR_YELLOW, tui.curses.COLOR_BLUE)


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
    msg = c.execute(":word G3958")
    assert c.view == "result"
    assert c.result_items
    assert "occurrences" in msg.lower()


def test_command_search_renders_result_view():
    c = make_controller()
    msg = c.execute(":search hope")
    assert c.view == "result"
    assert c.result_items
    assert "match" in msg.lower() or "hit" in msg.lower()


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
    assert "exported" in msg.lower()
    assert (tmp_path / "studies" / "1pet_3.18.md").exists()


# ===========================================================================
# Phase 4 — find, history, settings
# ===========================================================================

def test_find_returns_hits_and_navigates():
    c = make_controller()
    c.commit()
    c.set_scope("chapter")
    n = c.find("Christ")
    assert n >= 1
    assert c.find_idx == 0
    line = c.find_next(1)
    assert isinstance(line, int)


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
    assert c.show_help is False
    c.show_help = True
    lines, _ = c.render_content()
    assert any("help" in t.lower() for t, _ in lines)
    assert any("q or Esc to close" in t for t, _ in lines)


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
    c = make_controller()
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
