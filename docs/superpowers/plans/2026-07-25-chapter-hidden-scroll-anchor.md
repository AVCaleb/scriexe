# Chapter Hidden Scroll Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chapter scope visibly scroll on the first successful `j`/Down movement at content boundaries without exposing or changing the semantic verse focus.

**Architecture:** Store a private Chapter pane anchor containing the previous rendered focus row and a layout/content context signature. Chapter initializes with one centered draw, then follows rendered-row deltas; Window continues absolute centering, and `_draw_lines()` remains responsible for drawing and boundary clamping.

**Tech Stack:** Python 3.10+, curses, pytest 8+, PyInstaller 6

## Global Constraints

- Chapter must remain free of `KIND_FOCUS`, no-color focus markers, and `KIND_DIM`.
- `Controller.focus` must remain the source of truth for copy, note, bookmark, title, and persistence behavior.
- The first successful Chapter `j`/Down at the top boundary must visibly advance the viewport.
- Movement must use rendered-row deltas, not fixed terminal-line increments.
- Window, Verse, find navigation, and non-reading pane behavior must remain unchanged.
- Layout or rendered-content changes must reset the private anchor.
- Preserve unrelated uncommitted workspace changes.

## File Structure

- Modify `src/exeg/tui.py`: own private Chapter scroll-anchor state on `Controller` and apply it only in `_draw_pane()`.
- Modify `tests/test_tui2.py`: add sequential-draw regression coverage for immediate movement, reversal, and reset behavior.
- Existing `tests/test_tui.py`: retain visual-style and semantic-focus contracts.

---

### Task 1: Add the Delta-Following Chapter Anchor

**Files:**
- Modify: `src/exeg/tui.py:281-283,2434-2438`
- Modify: `tests/test_tui2.py:1347-1380`
- Test: `tests/test_tui.py`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Consumes: `_line_to_row(lines, line_idx, avail, color, wrap=True) -> int`
- Consumes: `_draw_lines(..., focus_line=-1, wrap=True, center=False) -> int`
- Produces: `Controller._chapter_scroll_anchor: tuple[tuple[int, int, int], int] | None`
- Produces: `_draw_pane(...) -> int` with delta-following Chapter behavior

- [ ] **Step 1: Write the failing sequential-draw regression test**

Add after `test_chapter_and_window_share_centered_focus_scrolling` in `tests/test_tui2.py`:

```python
def test_chapter_hidden_anchor_moves_on_first_down_and_resets(tmp_notes):
    class FakeWindow:
        def addstr(self, y, x, text, attr):
            pass

    screen = type("FakeScreen", (), {"stdscr": FakeWindow()})()
    lines = [(f"line {i}", tui.KIND_NORMAL) for i in range(30)]

    chapter = make_controller()
    chapter.scope = "chapter"
    scroll = tui._draw_pane(
        screen, chapter, lines, 0,
        top=0, body_h=9, x=0, w=80, scroll=0, color=False,
    )
    assert scroll == 0

    scroll = tui._draw_pane(
        screen, chapter, lines, 3,
        top=0, body_h=9, x=0, w=80, scroll=scroll, color=False,
    )
    assert scroll == 3

    scroll = tui._draw_pane(
        screen, chapter, lines, 0,
        top=0, body_h=9, x=0, w=80, scroll=scroll, color=False,
    )
    assert scroll == 0

    window = make_controller()
    window.scope = "window"
    scroll = tui._draw_pane(
        screen, window, lines, 0,
        top=0, body_h=9, x=0, w=80, scroll=0, color=False,
    )
    scroll = tui._draw_pane(
        screen, window, lines, 3,
        top=0, body_h=9, x=0, w=80, scroll=scroll, color=False,
    )
    assert scroll == 0

    scroll = tui._draw_pane(
        screen, chapter, lines, 3,
        top=0, body_h=7, x=0, w=80, scroll=0, color=False,
    )
    assert scroll == 0

    changed_lines = [("new", tui.KIND_NORMAL), *lines]
    scroll = tui._draw_pane(
        screen, chapter, changed_lines, 4,
        top=0, body_h=7, x=0, w=80, scroll=scroll, color=False,
    )
    assert scroll == 1
```

The Chapter assertions prove immediate three-row movement and reversal. Window remains clamped because it repeats absolute centering. Geometry reset reinitializes at `max(0, 3 - 7 // 2) == 0`; content reset reinitializes at `4 - 7 // 2 == 1` instead of applying a stale delta.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd /Users/caleb/Projects/exegesis
PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_tui2.py::test_chapter_hidden_anchor_moves_on_first_down_and_resets
```

Expected: FAIL because the second Chapter draw returns `0` instead of `3`.

- [ ] **Step 3: Add explicit private anchor state**

In `Controller.__init__`, immediately after `self.scope = "window"`, add:

```python
        self._chapter_scroll_anchor: tuple[tuple[int, int, int], int] | None = None
```

The nested context tuple contains pane height, available width, and a hash of rendered logical lines; the trailing integer is the previous rendered focus row.

- [ ] **Step 4: Implement Chapter delta-following in `_draw_pane`**

Replace `_draw_pane()` with:

```python
def _draw_pane(screen, c, lines, focus_line, top, body_h, x, w, scroll, color):
    if c.scope != "chapter":
        c._chapter_scroll_anchor = None
        return _draw_lines(screen, lines, top, body_h, x, w, scroll, color,
                           focus_line, wrap=True, center=c.scope == "window")

    find_active = bool(c.find_hits and c.find_idx >= 0)
    if find_active or focus_line < 0:
        c._chapter_scroll_anchor = None
        return _draw_lines(screen, lines, top, body_h, x, w, scroll, color,
                           focus_line, wrap=True, center=find_active)

    avail = max(8, w - x)
    focus_row = _line_to_row(lines, focus_line, avail, color, wrap=True)
    context = (body_h, avail, hash(tuple(lines)))
    previous = c._chapter_scroll_anchor

    if focus_row < 0 or previous is None or previous[0] != context:
        next_scroll = _draw_lines(
            screen, lines, top, body_h, x, w, scroll, color,
            focus_line, wrap=True, center=True,
        )
    else:
        next_scroll = _draw_lines(
            screen, lines, top, body_h, x, w,
            scroll + focus_row - previous[1], color,
            focus_line=-1, wrap=True, center=False,
        )

    c._chapter_scroll_anchor = (context, focus_row)
    return next_scroll
```

Do not modify `_render_verse()`, `move_focus()`, `_handle()`, or semantic-focus persistence.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
cd /Users/caleb/Projects/exegesis
PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_tui2.py::test_chapter_hidden_anchor_moves_on_first_down_and_resets \
  tests/test_tui2.py::test_chapter_and_window_share_centered_focus_scrolling \
  tests/test_tui.py::test_render_content_window_scope_has_focus_and_dim \
  tests/test_tui.py::test_render_content_chapter_scope_no_dim_or_focus_highlight \
  tests/test_tui.py::test_chapter_scope_scroll_tracks_focus
```

Expected: `5 passed`.

- [ ] **Step 6: Run complete verification and commit**

Run:

```bash
cd /Users/caleb/Projects/exegesis
.venv/bin/pytest -q
git diff --check
git diff -- src/exeg/tui.py tests/test_tui2.py
git add src/exeg/tui.py tests/test_tui2.py
git diff --cached --check
git commit -m "fix: make chapter scroll respond immediately"
```

Expected: the complete suite passes and only the two focused files are staged. Do not stage packaging, dependency, build, distribution, corpus, or backup-file changes.

- [ ] **Step 7: Rebuild and verify the local macOS arm64 archive**

Run:

```bash
cd /Users/caleb/Projects/exegesis
.venv/bin/python packaging/build_core_data.py --output build/core
.venv/bin/pyinstaller --clean --noconfirm packaging/scriexe.spec
artifact="dist/scriexe-darwin-arm64-$(git rev-parse --short HEAD).tar.gz"
rm -f "$artifact"
COPYFILE_DISABLE=1 tar -C dist -czf "$artifact" scriexe
tmp=$(mktemp -d)
tar -xzf "$artifact" -C "$tmp"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$tmp/scriexe/scriexe"
"$tmp/scriexe/scriexe" --version
EXEG_USER_ROOT="$tmp/user" "$tmp/scriexe/scriexe" passage "Jude 1:1" --versions cuvs,asv >/dev/null
rm -rf "$tmp"
shasum -a 256 "$artifact"
```

Expected: PyInstaller succeeds, the extracted executable passes signature and command smoke tests, and the final command prints the archive SHA-256.
