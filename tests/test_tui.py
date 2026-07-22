"""Unit tests for the pure Controller logic in exeg.tui (no curses)."""
from exeg import canon, tui


def make_controller():
    return tui.Controller()


# ---- defaults ----

def test_defaults_to_1pet_3_18_nav_visible():
    c = make_controller()
    assert c.focus.book().osis == "1Pet"
    assert c.focus.chapter == 3
    assert c.focus.verse == 18
    assert c.nav_visible is True
    assert c.nav_col == 0
    assert c.scope == "window"
    assert c.running is True


def test_local_default_versions_include_originals_and_cuvs():
    c = make_controller()
    assert "sblgnt" in c.versions       # 1Pet is NT
    assert "cuvs" in c.versions
    assert "esv" not in c.versions      # offline default


# ---- nav columns (off-by-one regression) ----

def test_book_column_value_is_one_based():
    c = make_controller()
    # focus is 1Pet; its index in BOOKS
    idx = next(i for i, b in enumerate(canon.BOOKS) if b.osis == "1Pet")
    assert c.column_value(0) == idx + 1
    assert c.column_items(0)[idx] == "1 Peter"


def test_drill_and_up_move_columns():
    c = make_controller()
    assert c.nav_col == 0
    c.drill(); assert c.nav_col == 1
    c.drill(); assert c.nav_col == 2
    c.drill(); assert c.nav_col == 3
    c.drill(); assert c.nav_col == 3   # clamped (4 columns now)
    c.up();   assert c.nav_col == 2
    c.up();   assert c.nav_col == 1
    c.up();   assert c.nav_col == 0
    c.up();   assert c.nav_col == 0    # clamped


def test_move_sel_in_books_column_changes_book():
    c = make_controller()
    c.nav_col = 0
    start_book = c.sel.book().osis
    c.move_sel(1)
    assert c.sel.book().osis != start_book
    # chapters/verses reset to 1 after a book change
    assert c.sel.chapter == 1 and c.sel.verse == 1


def test_move_sel_chapters_then_drill_to_verses():
    c = make_controller()
    c.nav_col = 1
    c.move_sel(1)                       # next chapter
    assert c.sel.chapter == 4
    c.drill()                           # -> verses column
    assert c.nav_col == 2
    items = c.column_items(2)
    assert c.column_value(2) == 1       # verse resets to 1 on chapter change
    assert len(items) > 0


# ---- commit / exit / toggle ----

def test_commit_copies_sel_to_focus_and_hides_nav():
    c = make_controller()
    c.nav_col = 1
    c.move_sel(1)                       # chapter 4
    c.commit()
    assert c.nav_visible is False
    assert c.focus.chapter == 4
    assert c.focus.book().osis == "1Pet"


def test_exit_nav_discards_selection_changes():
    c = make_controller()
    saved_ch = c.focus.chapter
    c.nav_col = 1
    c.move_sel(2)                       # roam to a different chapter
    c.exit_nav()
    assert c.nav_visible is False
    assert c.focus.chapter == saved_ch  # unchanged
    assert c.sel.chapter == saved_ch    # sel snapped back


def test_toggle_nav_roundtrip_restores_focus():
    c = make_controller()
    c.commit()                          # nav off, focus = 1Pet 3:18
    c.toggle_nav()                      # nav on, sel = focus
    assert c.nav_visible is True
    assert c.sel.chapter == 3 and c.sel.verse == 18
    c.toggle_nav()                      # nav off (exit)
    assert c.nav_visible is False


# ---- content focus movement ----

def test_move_focus_within_chapter():
    c = make_controller()
    c.commit()                          # content mode, 1Pet 3:18
    c.move_focus(1)
    assert c.focus.verse == 19
    c.move_focus(-1)
    assert c.focus.verse == 18
    c.move_focus(-100)                  # clamp to first
    keys = c.verse_list()
    assert (c.focus.chapter, c.focus.verse) == keys[0]


def test_move_focus_clamps_to_last():
    c = make_controller()
    c.commit()
    c.move_focus(10000)
    keys = c.verse_list()
    assert (c.focus.chapter, c.focus.verse) == keys[-1]


# ---- scopes ----

def test_cycle_scope_wraps():
    c = make_controller()
    assert c.scope == "window"
    c.cycle_scope(); assert c.scope == "chapter"
    c.cycle_scope(); assert c.scope == "verse"
    c.cycle_scope(); assert c.scope == "window"


def test_view_ref_respects_scope():
    c = make_controller()
    c.commit()
    c.scope = "verse"
    r = c.view_ref()
    assert r.chapter == 3 and r.verse == 18 and r.end_chapter == 3 and r.end_verse == 18
    c.scope = "window"
    c.window = 1
    r = c.view_ref()
    assert r.verse == 17 and r.end_verse == 19
    c.scope = "chapter"
    r = c.view_ref()
    assert r.verse == 1
    assert r.end_verse >= 22            # 1Pet 3 has >= 22 verses


def test_resize_window_clamps():
    c = make_controller()
    c.resize_window(-100); assert c.window == 1
    c.resize_window(1000); assert c.window == 40


# ---- rendering ----

def test_render_content_window_scope_has_focus_and_dim():
    c = make_controller()
    c.commit()
    c.scope = "window"
    c.window = 1
    lines, focus_line = c.render_content()
    assert focus_line >= 0
    kinds = [k for _, k in lines]
    assert tui.KIND_FOCUS in kinds
    assert tui.KIND_DIM in kinds
    # the focused heading line names 1Pet 3:18
    assert any("3:18" in t and k == tui.KIND_FOCUS for t, k in lines)


def test_render_content_chapter_scope_no_dim():
    c = make_controller()
    c.commit()
    c.scope = "chapter"
    lines, _ = c.render_content()
    kinds = {k for _, k in lines}
    assert tui.KIND_DIM not in kinds
    assert tui.KIND_FOCUS in kinds


def test_render_content_verse_scope_has_note_strip():
    c = make_controller()
    c.commit()
    c.scope = "verse"
    lines, _ = c.render_content()
    assert any(k == tui.KIND_NOTE for _, k in lines)


# ---- commands ----

def test_command_versions():
    c = make_controller()
    msg = c.execute(":versions sblgnt,cuvs,web")
    assert c.versions == ["sblgnt", "cuvs", "web"]
    assert "sblgnt" in msg


def test_command_versions_no_arg_shows_current():
    c = make_controller()
    msg = c.execute(":versions")
    assert "cuvs" in msg


def test_command_scope():
    c = make_controller()
    assert c.execute(":scope chapter").endswith("chapter")
    assert c.scope == "chapter"
    assert "bad" in c.execute(":scope bogus")


def test_command_passage_sets_study_set_and_focus():
    c = make_controller()
    msg = c.execute(":passage 1Pet 3:18-20")
    assert c.study_set is not None
    assert "1 Peter 3:18" in msg or "3:18" in msg
    # focus lands on the first verse of the range
    assert c.focus.chapter == 3 and c.focus.verse == 18
    assert c.nav_visible is False


def test_command_passage_no_arg_clears():
    c = make_controller()
    c.execute(":passage 1Pet 3:18-20")
    assert c.study_set is not None
    c.execute(":passage")
    assert c.study_set is None


def test_command_passage_bad_ref():
    c = make_controller()
    msg = c.execute(":passage NotABook 1:1")
    assert "bad" in msg.lower() or "cannot" in msg.lower()
    assert c.study_set is None


def test_command_help():
    c = make_controller()
    msg = c.execute(":help")
    assert msg == ""
    assert c.show_help is True


def test_command_quit_stops_running():
    c = make_controller()
    c.execute(":q")
    assert c.running is False


def test_command_word_search_render_results():
    c = make_controller()
    assert "occurrences" in c.execute(":word G3958").lower() or c.view == "result"
    assert c.view == "result"
    c.exit_result_view()
    assert "match" in c.execute(":search hope").lower() or c.view == "result"


def test_command_unknown():
    c = make_controller()
    msg = c.execute(":frobnicate")
    assert "unknown" in msg.lower()