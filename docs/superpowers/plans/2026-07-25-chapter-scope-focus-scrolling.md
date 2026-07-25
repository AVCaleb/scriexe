# Chapter Scope Focus Scrolling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chapter and Window scopes calculate the same centered focus-following scroll offset while Chapter remains visually unfocused.

**Architecture:** Keep the existing separation between verse rendering and pane positioning. `_render_verse()` continues to expose a logical `focus_line` without assigning Chapter focus styling; `_draw_pane()` selects centered scrolling for both `window` and `chapter`, delegating the shared calculation and boundary clamping to `_draw_lines()`.

**Tech Stack:** Python 3.10+, curses, pytest 8+

## Global Constraints

- Chapter scope must emit no `KIND_FOCUS`, no no-color focus marker, and no `KIND_DIM`.
- Window scope must retain its focus highlight and dimmed surrounding context.
- Window and Chapter scopes must use the same centered scrolling calculation.
- Centering must clamp at content boundaries without adding blank padding.
- Verse scope and non-reading panes must retain their existing scrolling behavior.
- Preserve unrelated uncommitted workspace changes.

## File Structure

- Modify `tests/test_tui2.py`: add a pane-level regression test covering shared Window/Chapter offsets, boundary clamping, and unchanged Verse behavior.
- Modify `src/exeg/tui.py`: expand `_draw_pane()`'s centered-scope predicate from Window alone to Window and Chapter.
- Existing `tests/test_tui.py`: retain the renderer contract proving Chapter has no focus or dim styling and Window still has both.

---

### Task 1: Share Centered Focus Scrolling Between Window and Chapter

**Files:**
- Modify: `tests/test_tui2.py`
- Modify: `src/exeg/tui.py:2434-2438`
- Test: `tests/test_tui.py`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Consumes: `_draw_pane(screen, c, lines, focus_line, top, body_h, x, w, scroll, color) -> int`
- Consumes: `_draw_lines(..., focus_line=-1, wrap=True, center=False) -> int`
- Produces: identical centered scroll offsets for `c.scope == "window"` and `c.scope == "chapter"`; unchanged non-centered offset for `c.scope == "verse"`

- [ ] **Step 1: Write the failing pane-level regression test**

Add this test near the existing `_draw_lines` scrolling test in `tests/test_tui2.py`:

```python
def test_chapter_and_window_share_centered_focus_scrolling(tmp_notes):
    class FakeWindow:
        def addstr(self, y, x, text, attr):
            pass

    screen = type("FakeScreen", (), {"stdscr": FakeWindow()})()
    lines = [(f"line {i}", tui.KIND_NORMAL) for i in range(20)]
    expected_by_focus = {0: 0, 10: 8, 19: 15}

    for focus_line, expected in expected_by_focus.items():
        offsets = {}
        for scope in ("window", "chapter", "verse"):
            c = make_controller()
            c.scope = scope
            offsets[scope] = tui._draw_pane(
                screen, c, lines, focus_line,
                top=0, body_h=5, x=0, w=80, scroll=0, color=False,
            )

        assert offsets["window"] == expected
        assert offsets["chapter"] == expected

    assert offsets["verse"] == 15

    c = make_controller()
    c.scope = "verse"
    assert tui._draw_pane(
        screen, c, lines, 10,
        top=0, body_h=5, x=0, w=80, scroll=0, color=False,
    ) == 6
```

The focus positions prove top clamping, middle centering (`10 - 5 // 2 == 8`), and bottom clamping (`20 - 5 == 15`). The final assertion proves Verse scope still uses keep-visible scrolling (`10 - 5 + 1 == 6`).

- [ ] **Step 2: Run the regression test and verify RED**

Run:

```bash
cd /Users/caleb/Projects/exegesis
PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_tui2.py::test_chapter_and_window_share_centered_focus_scrolling
```

Expected: FAIL at the middle Chapter assertion because Chapter returns `6` while Window returns `8`.

- [ ] **Step 3: Implement the minimal scope predicate change**

In `src/exeg/tui.py`, change `_draw_pane()` to:

```python
def _draw_pane(screen, c, lines, focus_line, top, body_h, x, w, scroll, color):
    center = c.scope in ("window", "chapter")
    return _draw_lines(screen, lines, top, body_h, x, w, scroll, color,
                       focus_line, wrap=True, center=center)
```

Do not change `_render_verse()`; its existing `is_highlighted = is_focus and self.scope != "chapter"` condition is what keeps Chapter focus invisible.

- [ ] **Step 4: Run focused behavior tests and verify GREEN**

Run:

```bash
cd /Users/caleb/Projects/exegesis
PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_tui2.py::test_chapter_and_window_share_centered_focus_scrolling \
  tests/test_tui.py::test_render_content_window_scope_has_focus_and_dim \
  tests/test_tui.py::test_render_content_chapter_scope_no_dim_or_focus_highlight \
  tests/test_tui.py::test_chapter_scope_scroll_tracks_focus
```

Expected: `4 passed`. This jointly proves matching positioning and differing visual styles.

- [ ] **Step 5: Run complete verification**

Run:

```bash
cd /Users/caleb/Projects/exegesis
.venv/bin/pytest -q
git diff --check
git status --short
```

Expected: the full Python suite passes; `git diff --check` emits no output; status shows only the intended `src/exeg/tui.py` and `tests/test_tui2.py` changes plus pre-existing unrelated workspace changes.

- [ ] **Step 6: Commit only the focused implementation**

Inspect the exact diff before staging, then commit the two relevant files:

```bash
cd /Users/caleb/Projects/exegesis
git diff -- src/exeg/tui.py tests/test_tui2.py
git add src/exeg/tui.py tests/test_tui2.py
git diff --cached --check
git commit -m "fix: center chapter scope on logical focus"
```

Do not stage packaging, dependency, build, distribution, corpus, or backup-file changes.
