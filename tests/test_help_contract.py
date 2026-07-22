"""Behavioral contract for every externally visible Help promise."""
import pytest

from exeg import corpus, tui


def controller(lang="en"):
    c = tui.Controller()
    c.lang = lang
    return c


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_help_documents_current_search_and_command_editor_contract(lang):
    text = "\n".join(line for line, _kind in tui.help_lines(lang))
    assert "n/N" not in text
    for token in ("j /", "Enter", "Esc", "[ASV]", "[CUVS]", "Home", "Ctrl-A",
                  "End", "Ctrl-E", "Backspace", "Delete", "Ctrl-U", "Ctrl-K"):
        assert token in text
    assert ("currently enabled" in text if lang == "en" else "当前已启用" in text)
    assert ("absolute" in text if lang == "en" else "绝对路径" in text)
    assert ("Hebrew" in text and "right edge" in text if lang == "en" else
            "希伯来文" in text and "右边缘" in text)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_help_shows_current_absolute_studies_directory(lang, tmp_path, monkeypatch):
    target = tmp_path / "user-data" / "studies"
    monkeypatch.setattr(corpus, "studies_dir", lambda: target)
    text = "\n".join(line for line, _kind in tui.help_lines(lang))
    assert str(target.resolve()) in text


def test_plain_q_is_contextual_but_colon_q_always_exits():
    c = controller()
    tui._handle(None, c, ord("q"), 0, [], -1, 20)
    assert c.running is True and c.nav_visible is False

    c.open_settings()
    tui._handle(None, c, ord("q"), 0, [], -1, 20)
    assert c.running is True and c.view == "verse"

    c.view = "result"
    c.result_items = [(c.focus.book_idx, c.focus.chapter, c.focus.verse)]
    tui._handle(None, c, ord("q"), 0, [], -1, 20)
    assert c.running is True and c.view == "verse"

    c.show_help = True
    tui._handle(None, c, ord("q"), 0, [], -1, 20)
    assert c.running is True and c.show_help is False

    c.execute(":q")
    assert c.running is False


def test_result_h_returns_without_changing_pre_search_verse():
    c = controller()
    c.nav_visible = False
    before = c.focus
    c.view = "result"
    c.result_items = [(0, 1, 1)]
    c.result_lines = [("search", tui.KIND_HEADER), ("", tui.KIND_NOTE),
                      ("[ASV] Gen 1:1  result", tui.KIND_OCCUR)]
    tui._handle(None, c, ord("h"), 0, c.result_lines, 2, 20)
    assert c.view == "verse"
    assert c.focus == before


def test_help_status_promises_only_keys_handled_by_help_mode():
    for lang in ("en", "zh"):
        c = controller(lang)
        c.show_help = True
        status = tui._status(c)
        assert "j/k/↑/↓" in status and "q/Esc" in status
        assert all(token not in status for token in ("NORMAL", "Tab", "+/-", " i ", " / "))
