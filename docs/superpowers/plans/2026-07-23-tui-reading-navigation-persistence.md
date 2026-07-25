# TUI Reading, Navigation, Persistence, and Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scriexe retain the user's reading position, start new users at Matthew 1:1, provide faster chapter/NAV movement and verse copying, offer an opt-in Vim-style note copy/paste keymap, keep Settings selections visible, and render every Scripture character.

**Architecture:** Keep behavior in the existing pure `Controller` and small module-level terminal adapters. Persist a validated `last_read` object by merging `notes/_meta.json`; reuse the current focus-line scrolling mechanism for selectable pages; fix clipping at the final drawing boundary rather than altering corpus text. Clipboard access remains dependency-free and platform-specific behind a testable helper.

**Tech Stack:** Python 3.10+, curses, stdlib subprocess/shutil/platform, pytest, existing PyInstaller and Node launcher tooling.

## Global Constraints

- Preserve all pre-existing uncommitted release/packaging changes in the source checkout.
- Do not alter Scripture corpus text unless the source-to-normalized audit finds an independent mismatch.
- `[` means previous chapter and `]` means next chapter; chapter jumps open verse 1 and cross canonical book boundaries.
- NAV `Ctrl-U`/`Ctrl-D` moves exactly five items; outside NAV it retains half-screen scrolling.
- `y` copies the highlighted single verse reference plus all displayed translations outside note editing.
- Optional Vim note keys are disabled by default and provide `yy`, Visual yank, and `p/P` system-clipboard paste only for the inline editor.
- First-run fallback is Matthew 1:1; configured users restore only a valid committed `last_read` value.
- No new runtime or packaging dependency.
- Stop before package publication, release creation, tag push, or npm publish.

---

## File Structure

- Modify `src/exeg/tui.py`: controller state, key routing, selected-line focus, bidirectional clipboard adapter, optional Vim note modes, drawing boundary, Help text.
- Modify `src/exeg/i18n.py`: bilingual clipboard/Vim status, Settings explanation, and updated mode hints.
- Modify `tests/test_tui2.py`: focused controller, renderer, clipboard, persistence, Vim note editing, and key-routing regressions.
- Modify `tests/test_help_contract.py`: externally documented shortcut contract.
- Use `docs/superpowers/specs/2026-07-23-tui-reading-navigation-persistence-design.md` as the approved behavior source.

### Task 1: Metadata-Safe Reading Position and Matthew First Run

**Files:**
- Modify: `src/exeg/tui.py:26-29,175-251,307-318,425-435,1159-1180`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Produces: `_default_node() -> Node`, `_node_from_meta(meta: dict, intro: bool) -> Node`, `Controller._persist_reading_position() -> None`
- Preserves: `Controller(versions=None, intro=False)` public construction API

- [ ] **Step 1: Isolate every TUI test from real user metadata**

Make the existing `tmp_notes` fixture autouse, and keep legacy 1 Peter-focused tests explicit through their helper:

```python
@pytest.fixture(autouse=True)
def tmp_notes(tmp_path, monkeypatch):
    """Redirect every TUI test's notes and metadata to a temporary directory."""
    monkeypatch.setattr(notes, "notes_root", lambda: tmp_path / "notes")
    return tmp_path / "notes"


def make_controller():
    c = tui.Controller(intro=True)
    c._set_focus_state(tui.Node(tui._osis_index("1Pet"), 3, 18))
    c.lang = "en"
    return c
```

This keeps existing word-study fixtures on 1 Peter 3:18 while all direct/new controllers exercise the Matthew default. Explicit `tmp_notes` test parameters continue to receive the same autouse fixture value.

- [ ] **Step 2: Write failing startup and metadata tests**

Add tests using isolated metadata:

```python
def test_unconfigured_controller_starts_at_matthew_1_1(tmp_notes):
    c = tui.Controller(intro=True)
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Matt", 1, 1)


def test_configured_controller_restores_last_committed_verse(tmp_notes):
    notes.write_meta({"setup_done": True,
                      "last_read": {"book": "Isa", "chapter": 5, "verse": 7}})
    c = tui.Controller()
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Isa", 5, 7)


def test_invalid_last_read_falls_back_to_matthew_1_1(tmp_notes):
    notes.write_meta({"setup_done": True,
                      "last_read": {"book": "NoBook", "chapter": 999, "verse": 0}})
    c = tui.Controller()
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Matt", 1, 1)


def test_goto_persists_focus_without_overwriting_preferences(tmp_notes):
    notes.write_meta({"setup_done": True, "lang": "zh", "translations": ["cuvs"]})
    c = tui.Controller()
    c.goto(tui.Node(tui._osis_index("Isa"), 5, 7))
    meta = notes.read_meta()
    assert meta["last_read"] == {"book": "Isa", "chapter": 5, "verse": 7}
    assert meta["setup_done"] is True
    assert meta["lang"] == "zh" and meta["translations"] == ["cuvs"]


def test_preference_persistence_preserves_setup_and_last_read(tmp_notes):
    notes.write_meta({"setup_done": True,
                      "last_read": {"book": "Matt", "chapter": 2, "verse": 3}})
    c = tui.Controller()
    c.execute(":set window 8")
    meta = notes.read_meta()
    assert meta["setup_done"] is True
    assert meta["last_read"] == {"book": "Matt", "chapter": 2, "verse": 3}
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'starts_at_matthew or restores_last or invalid_last or persists_focus or persistence_preserves'
```

Expected: failures showing the hard-coded 1 Peter 3:18 start, no `last_read` restoration, and metadata replacement.

- [ ] **Step 4: Implement validated initialization and merged metadata writes**

In `src/exeg/tui.py`, replace the default constants and initialize from metadata once:

```python
DEFAULT_BOOK = "Matt"
DEFAULT_CHAPTER = 1
DEFAULT_VERSE = 1


def _default_node() -> Node:
    return Node(_osis_index(DEFAULT_BOOK), DEFAULT_CHAPTER, DEFAULT_VERSE)


def _node_from_meta(meta: dict, intro: bool = False) -> Node:
    if intro or not meta.get("setup_done"):
        return _default_node()
    value = meta.get("last_read")
    if not isinstance(value, dict):
        return _default_node()
    try:
        book_idx = _osis_index(str(value["book"]))
        chapter = int(value["chapter"])
        verse = int(value["verse"])
        book = canon.BOOKS[book_idx]
        if not 1 <= chapter <= book.chapters:
            raise ValueError
        maximum = _max_verse(book, chapter)
        if verse < 1 or (maximum and verse > maximum):
            raise ValueError
        return Node(book_idx, chapter, verse)
    except (KeyError, TypeError, ValueError, StopIteration):
        return _default_node()
```

Move `m = notes.read_meta()` to the beginning of `Controller.__init__`, derive all initial node fields from `_node_from_meta(m, intro)`, and remove the later duplicate read.

Add merged writes:

```python
def _write_meta_updates(**updates) -> None:
    meta = notes.read_meta()
    meta.update(updates)
    notes.write_meta(meta)


def _persist_reading_position(self):
    _write_meta_updates(last_read={"book": self.focus.book().osis,
                                   "chapter": self.focus.chapter,
                                   "verse": self.focus.verse})
```

Call `_persist_reading_position()` at the end of `goto`. Change `_persist_meta`, `finish_intro`, and setup completion paths to merge values rather than replace the dictionary. `finish_intro` sets the default focus and persists both `setup_done=True` and `last_read` for Matthew 1:1.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 6: Run existing setup/settings regressions**

Run:

```bash
.venv/bin/pytest -q tests/test_setup.py tests/test_tui2.py -k 'intro or settings or restore_defaults or controller_lang or last_read or persistence'
```

Expected: PASS with onboarding and settings metadata retained.

- [ ] **Step 7: Commit the task**

```bash
git add src/exeg/tui.py tests/test_tui2.py
git commit -m "fix: restore the last reading position"
```

### Task 2: Chapter Movement and Five-Item NAV Movement

**Files:**
- Modify: `src/exeg/tui.py:828-840,895-910,2345-2440`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Produces: `Controller.move_chapter(delta: int) -> None`
- Reuses: `Controller.move_sel(delta: int)` and `Controller.goto(...)`

- [ ] **Step 1: Write failing controller and key-routing tests**

```python
def test_move_chapter_crosses_book_boundaries_and_opens_verse_one(tmp_notes):
    c = tui.Controller(intro=True)
    c.goto(tui.Node(tui._osis_index("Matt"), 2, 10))
    c.move_chapter(-1)
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Matt", 1, 1)
    c.move_chapter(-1)
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Mal", 4, 1)
    c.move_chapter(1)
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Matt", 1, 1)


def test_move_chapter_clamps_at_canonical_endpoints(tmp_notes):
    c = tui.Controller(intro=True)
    c.goto(tui.Node(tui._osis_index("Gen"), 1, 1))
    c.move_chapter(-1)
    assert (c.focus.book().osis, c.focus.chapter) == ("Gen", 1)
    c.goto(tui.Node(tui._osis_index("Rev"), 22, 1))
    c.move_chapter(1)
    assert (c.focus.book().osis, c.focus.chapter) == ("Rev", 22)


def test_brackets_route_to_previous_and_next_chapter(tmp_notes):
    c = tui.Controller(intro=True)
    c.nav_visible = False
    tui._handle(None, c, ord("]"), 0, [], -1, 20)
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Matt", 2, 1)
    tui._handle(None, c, ord("["), 0, [], -1, 20)
    assert (c.focus.book().osis, c.focus.chapter, c.focus.verse) == ("Matt", 1, 1)


def test_nav_ctrl_u_ctrl_d_move_five_items(tmp_notes):
    c = tui.Controller(intro=True)
    c.nav_col = 0
    assert c.column_value(0) == tui._osis_index("Matt") + 1
    tui._handle(None, c, 4, 0, [], -1, 20)
    assert c.column_value(0) == tui._osis_index("Matt") + 6
    tui._handle(None, c, 21, 0, [], -1, 20)
    assert c.column_value(0) == tui._osis_index("Matt") + 1
```

- [ ] **Step 2: Run tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'move_chapter or brackets_route or nav_ctrl'
```

Expected: `move_chapter` missing and key handlers leave state unchanged.

- [ ] **Step 3: Implement chapter traversal**

```python
def move_chapter(self, delta: int):
    if self.view != "verse" or delta == 0:
        return
    book_idx = self.focus.book_idx
    chapter = self.focus.chapter + (1 if delta > 0 else -1)
    if chapter < 1:
        if book_idx == 0:
            chapter = 1
        else:
            book_idx -= 1
            chapter = canon.BOOKS[book_idx].chapters
    elif chapter > canon.BOOKS[book_idx].chapters:
        if book_idx == len(canon.BOOKS) - 1:
            chapter = canon.BOOKS[book_idx].chapters
        else:
            book_idx += 1
            chapter = 1
    self.goto(Node(book_idx, chapter, 1), view="verse", word_idx=None)
```

Route `[`/`]` in ordinary verse mode. Inside the existing NAV branch, route key code `21` to `move_sel(-5)` and key code `4` to `move_sel(5)` before returning.

- [ ] **Step 4: Verify GREEN and reading-mode Ctrl-U/Ctrl-D compatibility**

Run:

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'move_chapter or brackets_route or nav_ctrl or help_keys_scroll'
```

Expected: PASS. Existing non-NAV scroll return values remain unchanged.

- [ ] **Step 5: Commit the task**

```bash
git add src/exeg/tui.py tests/test_tui2.py
git commit -m "feat: add fast chapter and navigator movement"
```

### Task 3: Keep Settings and Onboarding Selections Visible

**Files:**
- Modify: `src/exeg/tui.py:436-459,545-582,1745-1755`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Changes: `render_intro()` and `render_settings()` return the selected logical line index as their second tuple item.
- Reuses: `_draw_lines(..., focus_line=...)` scrolling behavior.

- [ ] **Step 1: Write failing selected-line tests**

```python
def test_settings_focus_line_tracks_selected_item(tmp_notes):
    c = tui.Controller(intro=True)
    c.open_settings()
    c.settings_cursor = c._selectable_settings_indexes()[-1]
    lines, focus_line = c.render_settings()
    assert "Restore all settings" in lines[focus_line][0]


def test_intro_focus_line_tracks_begin_action(tmp_notes):
    c = tui.Controller(intro=True)
    c.intro_cursor = c._selectable_intro_indexes()[-1]
    lines, focus_line = c.render_intro()
    assert "Begin" in lines[focus_line][0]


def test_small_settings_pane_scrolls_selected_row_into_view(tmp_notes):
    c = tui.Controller(intro=True)
    c.open_settings()
    c.settings_cursor = c._selectable_settings_indexes()[-1]
    lines, focus_line = c.render_settings()

    class FakeWindow:
        def __init__(self):
            self.writes = []
        def addstr(self, y, x, text, attr):
            self.writes.append((y, text))

    screen = type("FakeScreen", (), {})()
    screen.stdscr = FakeWindow()
    scroll = tui._draw_lines(screen, lines, 1, 5, 0, 80, 0, True, focus_line)
    assert scroll > 0
```

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'focus_line_tracks or small_settings_pane'
```

Expected: focus remains fixed at line 2 and scroll remains at the top.

- [ ] **Step 3: Track selected output lines during rendering**

In each renderer, initialize `focus_line = -1`; immediately after appending a selectable row, set it when `sel` is true, then return `(lines, focus_line)`. In `run()`, change the onboarding draw call to pass its returned focus line:

```python
scroll = _draw_lines(screen, lines, top, body_h, 0, w, 0, color,
                     focus_line)
```

Settings already flows through `_draw_pane`, so its corrected return value activates existing focus scrolling.

- [ ] **Step 4: Verify GREEN**

Run the Step 2 command plus:

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'intro or settings'
```

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add src/exeg/tui.py tests/test_tui2.py
git commit -m "fix: keep settings selection visible"
```

### Task 4: Prevent Full-Width Scripture Character Loss

**Files:**
- Modify: `src/exeg/tui.py:1685-1695`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Preserves: `_put(win, y, x, s, attr, maxw)`
- Changes: clipping capacity is full width except on the actual terminal bottom row.

- [ ] **Step 1: Write the exact Isaiah 5:7 131-column regression**

```python
def test_put_does_not_drop_final_wide_character_from_wrapped_body():
    body = ("万军之耶和华的葡萄园就是 以色列家； 他所喜爱的树就是 犹大人。 "
            "他指望的是公平， 谁知倒有暴虐； 指望的是公义， 谁知倒有冤声。")
    logical = tui._version_line("和合本", body)
    rows, _ = tui._build_rows([(logical, tui.KIND_NORMAL)], 131, True, True)
    assert rows[0][0].endswith("声") and rows[1][0].endswith("。")

    class FakeWindow:
        def __init__(self):
            self.writes = []
        def getmaxyx(self):
            return (20, 131)
        def addstr(self, y, x, text, attr):
            self.writes.append(text)

    win = FakeWindow()
    for y, (text, _kind) in enumerate(rows):
        tui._put(win, y, 0, text, 0, 131)
    assert win.writes[0].endswith("声")
    assert "冤声。" in "".join(part.strip() for part in win.writes)
```

Add a lower-right safety test proving `_put` still reserves one cell only when `y == height - 1`. Update the existing generic clipping assertion to the corrected full remaining width:

```python
def test_put_clips_to_available_terminal_cells():
    class FakeWindow:
        def __init__(self):
            self.writes = []
        def getmaxyx(self):
            return (20, 20)
        def addstr(self, y, x, text, attr):
            self.writes.append((y, x, text, attr))

    win = FakeWindow()
    tui._put(win, 0, 10, "中文中文中文中文中文", 0, 20)
    assert _terminal_cells(win.writes[0][2]) <= 10


def test_put_reserves_only_the_terminal_lower_right_cell():
    class FakeWindow:
        def __init__(self):
            self.writes = []
        def getmaxyx(self):
            return (20, 20)
        def addstr(self, y, x, text, attr):
            self.writes.append((y, x, text, attr))

    win = FakeWindow()
    tui._put(win, 19, 10, "abcdefghij", 0, 20)
    assert win.writes[0][2] == "abcdefghi"
```

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'drop_final_wide or lower_right'
```

Expected: first write ends with `冤`, reproducing the reported missing `声`.

- [ ] **Step 3: Fix clipping at the actual terminal boundary**

Replace unconditional `maxw - x - 1` capacity with:

```python
capacity = max(0, maxw - x)
try:
    height, _width = win.getmaxyx()
except (AttributeError, curses.error):
    height = -1
if y == height - 1:
    capacity = max(0, capacity - 1)
s = _slice_cells(s, capacity)
```

Keep the existing empty-string guard and caught `curses.error` behavior.

- [ ] **Step 4: Verify renderer tests GREEN**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'drop_final_wide or lower_right or Unicode or wrap or put_clips'
```

Expected: PASS.

- [ ] **Step 5: Run an all-CUVS source normalization audit**

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from exeg import canon, corpus
from exeg.usfm import parse_usfm

seen = set()
mismatches = []
for path in sorted(Path("data/sources/cmn-cu89s").glob("*.usfm")):
    code, parsed = parse_usfm(path.read_text(encoding="utf-8-sig"))
    osis = canon.USFM_TO_OSIS.get(code)
    if osis is None:
        continue
    seen.add(osis)
    normalized = corpus.read_verses("cuvs", osis)
    if parsed != normalized:
        expected = {(v.chapter, v.verse): v.text for v in parsed}
        actual = {(v.chapter, v.verse): v.text for v in normalized}
        keys = sorted(set(expected) | set(actual))
        mismatches.extend(
            f"{osis} {ch}:{verse}: {expected.get((ch, verse))!r} != {actual.get((ch, verse))!r}"
            for ch, verse in keys
            if expected.get((ch, verse)) != actual.get((ch, verse))
        )
print(f"matched books: {len(seen)}; mismatches: {len(mismatches)}")
if mismatches:
    raise SystemExit("\n".join(mismatches[:50]))
assert seen == {book.osis for book in canon.BOOKS}
PY
```

Expected: `matched books: 66; mismatches: 0`. Record mismatch references if any before considering data changes.

- [ ] **Step 6: Run a renderer-loss audit across realistic widths**

```bash
.venv/bin/python - <<'PY'
from exeg import canon, corpus, tui

class FakeWindow:
    def __init__(self, width):
        self.width = width
        self.writes = []
    def getmaxyx(self):
        return (1000, self.width)
    def addstr(self, y, x, text, attr):
        self.writes.append(text)

for width in (40, 60, 80, 100, 120, 131, 140, 160, 200):
    clipped = []
    for book in canon.BOOKS:
        for verse in corpus.read_verses("cuvs", book.osis):
            logical = tui._version_line("和合本", verse.text)
            rows, _ = tui._build_rows([(logical, tui.KIND_NORMAL)], width, True, True)
            win = FakeWindow(width)
            for y, (row, _kind) in enumerate(rows):
                tui._put(win, y, 0, row, 0, width)
            if win.writes != [row for row, _kind in rows]:
                clipped.append(f"{book.osis} {verse.chapter}:{verse.verse}")
    print(f"width {width}: {len(clipped)} clipped rows")
    assert not clipped, clipped[:20]
PY
```

Expected after fix: `0 clipped rows` at every width.

- [ ] **Step 7: Commit the task**

```bash
git add src/exeg/tui.py tests/test_tui2.py
git commit -m "fix: preserve wrapped Scripture characters"
```

### Task 5: Copy the Highlighted Verse

**Files:**
- Modify: `src/exeg/tui.py:10-18,625-695,2267-2440`
- Modify: `src/exeg/i18n.py:8-45`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Produces: `_clipboard_command(system=None, which=shutil.which) -> list[str] | None`
- Produces: `_clipboard_read_command(system=None, which=shutil.which) -> list[str] | None`
- Produces: `_copy_clipboard(text: str, ...) -> tuple[bool, str]`
- Produces: `_read_clipboard(...) -> tuple[str | None, str]`
- Produces: `Controller.highlighted_verse_text() -> str`, `Controller.copy_highlighted_verse() -> None`

- [ ] **Step 1: Write failing formatting, adapter, and key tests**

```python
def test_highlighted_verse_text_contains_reference_and_visible_versions(tmp_notes):
    c = tui.Controller(intro=True)
    c.nav_visible = False
    c.translations = ["cuvs", "asv"]
    text = c.highlighted_verse_text()
    assert text.startswith("Matthew 1:1 · 太 1:1")
    assert "和合本" in text and "ASV" in text


def test_nav_copy_formats_preview_selection(tmp_notes):
    c = tui.Controller(intro=True)
    c._set_col_value(0, tui._osis_index("Isa") + 1)
    c.chapter, c.verse = 5, 7
    c.sel = tui.Node(tui._osis_index("Isa"), 5, 7)
    assert c.highlighted_verse_text().startswith("Isaiah 5:7")
    assert c.focus.book().osis == "Matt"


@pytest.mark.parametrize("system, available, expected", [
    ("Darwin", {"pbcopy"}, ["pbcopy"]),
    ("Windows", {"clip"}, ["clip"]),
    ("Linux", {"wl-copy"}, ["wl-copy"]),
    ("Linux", {"xclip"}, ["xclip", "-selection", "clipboard"]),
    ("Linux", {"xsel"}, ["xsel", "--clipboard", "--input"]),
])
def test_clipboard_command_mapping(system, available, expected):
    which = lambda name: f"/bin/{name}" if name in available else None
    assert tui._clipboard_command(system, which) == expected


@pytest.mark.parametrize("system, available, expected", [
    ("Darwin", {"pbpaste"}, ["pbpaste"]),
    ("Windows", {"powershell"}, ["powershell", "-NoProfile", "-Command",
                                  "Get-Clipboard -Raw"]),
    ("Linux", {"wl-paste"}, ["wl-paste", "--no-newline"]),
    ("Linux", {"xclip"}, ["xclip", "-selection", "clipboard", "-o"]),
    ("Linux", {"xsel"}, ["xsel", "--clipboard", "--output"]),
])
def test_clipboard_read_command_mapping(system, available, expected):
    which = lambda name: f"/bin/{name}" if name in available else None
    assert tui._clipboard_read_command(system, which) == expected


def test_y_copies_highlighted_verse_without_shell(tmp_notes, monkeypatch):
    c = tui.Controller(intro=True)
    c.nav_visible = False
    copied = []
    monkeypatch.setattr(tui, "_copy_clipboard",
                        lambda text: (copied.append(text) or True, ""))
    tui._handle(None, c, ord("y"), 0, [], -1, 20)
    assert copied and copied[0].startswith("Matthew 1:1")
    assert "copied" in c.message.lower()


def test_clipboard_failure_is_nonfatal_status(tmp_notes, monkeypatch):
    c = tui.Controller(intro=True)
    c.nav_visible = False
    monkeypatch.setattr(tui, "_copy_clipboard",
                        lambda text: (False, "no clipboard command found"))
    tui._handle(None, c, ord("y"), 0, [], -1, 20)
    assert c.running is True
    assert "failed" in c.message.lower()
```

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'highlighted_verse_text or nav_copy or clipboard_command or y_copies or clipboard_failure'
```

Expected: missing helper/method failures and no `y` action.

- [ ] **Step 3: Implement platform clipboard adapter**

Import `platform` and `shutil`. Implement write and read command choice in the approved platform priority order without shell invocation. `_copy_clipboard` calls:

```python
result = subprocess.run(command, input=text, text=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        check=False)
```

Return `(True, "")` only for exit code zero; return `(False, useful_message)` for no command, non-zero exit, or `OSError`. `_read_clipboard` runs the read command with `capture_output=True, text=True, check=False`, returning `(stdout, "")` on success and `(None, useful_message)` on failure.

- [ ] **Step 4: Implement pure highlighted-verse formatting and controller action**

Use `self.shown()` to select NAV preview versus committed focus. Construct a single-verse `refs.Ref`, call `_gather(ref, self.effective_versions())`, and append only available translation text in effective-version order:

```python
lines = [f"{book.en} {chapter}:{verse} · {book.zh_abbr} {chapter}:{verse}"]
for version in versions:
    text = texts.get(version, {}).get((chapter, verse))
    if text:
        lines.append(f"{display.LABELS.get(version, version.upper())}  {text}")
return "\n".join(lines) + "\n"
```

`copy_highlighted_verse` calls the adapter and sets localized `copied_verse` or `copy_failed` status. Route `y` in NAV and ordinary verse mode, but not in editing, onboarding, Help, Settings, Word, or Results.

- [ ] **Step 5: Add bilingual messages and status hints**

In `src/exeg/i18n.py`, add:

```python
"copied_verse": {"en": "copied {ref}", "zh": "已复制 {ref}"},
"copy_failed": {"en": "copy failed: {e}", "zh": "复制失败：{e}"},
```

Update `nav_hint` and `normal_hint` to mention `y copy` / `y 复制` without removing existing controls.

- [ ] **Step 6: Verify GREEN**

Run the Step 2 command. Expected: PASS and no real clipboard modification because the adapter is mocked in key-routing tests.

- [ ] **Step 7: Commit the task**

```bash
git add src/exeg/tui.py src/exeg/i18n.py tests/test_tui2.py
git commit -m "feat: copy the highlighted verse"
```

### Task 6: Opt-In Vim Note Copy/Paste Keymap

**Files:**
- Modify: `src/exeg/tui.py:207-224,461-582,965-1065,1745-1810,2112-2185`
- Modify: `src/exeg/i18n.py:8-90`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Produces: persisted `Controller.vim_keys: bool`, default `False`
- Produces: `Controller.note_mode` values `"insert" | "normal" | "visual" | "visual_line"`
- Produces: `Controller.note_selection_range() -> tuple[tuple[int, int], tuple[int, int]] | None`
- Produces: `Controller.yank_note_selection(linewise: bool = False) -> tuple[bool, str]`
- Produces: `Controller.paste_note_text(text: str, before: bool = False, replace_selection: bool = False) -> None`
- Preserves: current non-Vim inline editing and popup editing when the setting is disabled or inapplicable

- [ ] **Step 1: Write failing Settings/default/persistence tests**

```python
def test_vim_note_keys_default_off_and_load_from_meta(tmp_notes):
    assert tui.Controller(intro=True).vim_keys is False
    notes.write_meta({"vim_keys": True})
    assert tui.Controller().vim_keys is True


def test_settings_explains_and_toggles_vim_note_keys(tmp_notes):
    c = tui.Controller(intro=True)
    c.open_settings()
    items = c.settings_items()
    index = next(i for i, item in enumerate(items) if item.get("key") == "vim_keys")
    assert "copy" in items[index + 1]["label"].lower()
    assert "paste" in items[index + 1]["label"].lower()
    c.settings_cursor = index
    c.toggle_settings()
    assert c.vim_keys is True
    assert notes.read_meta()["vim_keys"] is True
```

For the Chinese explanation, set `c.lang = "zh"` and assert `复制` and `粘贴` occur in the note immediately after the checkbox.

- [ ] **Step 2: Run Settings tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'vim_note_keys or settings_explains'
```

Expected: `vim_keys` and its Settings item do not exist.

- [ ] **Step 3: Implement the opt-in setting without changing default editing**

Initialize and load:

```python
self.vim_keys = bool(m.get("vim_keys", False))
self.note_mode = "insert"
self.note_anchor: tuple[int, int] | None = None
self.note_pending = ""
```

Add a Settings checkbox followed by a localized note:

```python
{"type": "bool", "key": "vim_keys", "value": "on",
 "label": tr(self.lang, "vim_keys_label"), "active": self.vim_keys},
{"type": "note", "label": tr(self.lang, "vim_keys_explain")},
```

Toggle `vim_keys`, include it in merged `_persist_meta`, and add `"vim_keys": False` to `DEFAULT_SETTINGS`. Add translations:

```python
"vim_keys_label": {"en": "Vim-style note keybindings",
                   "zh": "Vim 风格笔记键位"},
"vim_keys_explain": {
    "en": "Optional: Normal/Visual navigation, selection, system clipboard copy and paste",
    "zh": "可选：使用 Normal/Visual 导航、选择及系统剪贴板复制粘贴",
},
```

Run the Step 2 command. Expected: PASS, while existing editor tests still pass unchanged.

- [ ] **Step 4: Write failing mode-transition, movement, and exit tests**

```python
def vim_editor_controller():
    c = make_controller()
    c.commit()
    c.vim_keys = True
    c.begin_edit()
    return c


def test_vim_escape_enters_normal_and_i_a_return_to_insert(tmp_notes):
    c = vim_editor_controller()
    c.insert_char("abc")
    tui._handle_vim_note_key(None, c, "\x1b")
    assert c.editing is True and c.note_mode == "normal"
    tui._handle_vim_note_key(None, c, "i")
    assert c.note_mode == "insert"
    tui._handle_vim_note_key(None, c, "\x1b")
    tui._handle_vim_note_key(None, c, "a")
    assert c.note_mode == "insert" and c.note_cx == 3


def test_vim_normal_movement_supports_hjkl_zero_dollar_gg_G(tmp_notes):
    c = vim_editor_controller()
    c.note_lines = ["abc", "def", "ghi"]
    c.note_cy, c.note_cx, c.note_mode = 1, 2, "normal"
    for key in ("h", "0", "$", "j", "k"):
        tui._handle_vim_note_key(None, c, key)
    assert (c.note_cy, c.note_cx) == (1, 2)
    tui._handle_vim_note_key(None, c, "g")
    tui._handle_vim_note_key(None, c, "g")
    assert c.note_cy == 0
    tui._handle_vim_note_key(None, c, "G")
    assert c.note_cy == 2


def test_vim_ZZ_saves_and_ZQ_discards(tmp_notes):
    c = vim_editor_controller()
    c.note_lines = ["save me"]
    c.note_mode = "normal"
    tui._handle_vim_note_key(None, c, "Z")
    tui._handle_vim_note_key(None, c, "Z")
    assert c.editing is False
    assert "save me" in notes.read_verse("1Pet", 3, 18)

    c = vim_editor_controller()
    c.note_lines = ["discard me"]
    c.note_mode = "normal"
    tui._handle_vim_note_key(None, c, "Z")
    tui._handle_vim_note_key(None, c, "Q")
    assert c.editing is False
    assert "discard me" not in notes.read_verse("1Pet", 3, 18)
```

Test `:wq` and `:q!` by mocking `_prompt_line` to return each command when `:` is handled in Normal mode.

- [ ] **Step 5: Run mode tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'vim_escape or vim_normal_movement or vim_ZZ or vim_colon'
```

Expected: Vim key handler and modes are missing.

- [ ] **Step 6: Implement focused Vim mode dispatch**

Keep the current `_edit_loop` code as the disabled/default path. When `c.vim_keys` is true and `_popup` is false, dispatch key input to `_handle_vim_note_key(screen, c, key)`.

Implement:

- Insert: preserve all existing character/newline/backspace/arrow behavior; Esc sets `note_mode="normal"` without ending edit.
- Normal/Visual movement: `h/l` and Left/Right call `cursor_move(0, ±1)`; `j/k` and Up/Down call `cursor_move(±1, 0)`; `0` sets column zero; `$` sets column to current line length; pending `gg` moves to first line; `G` moves to last line.
- `i` enters Insert at the current cursor; `a` advances one character when possible and enters Insert.
- pending `ZZ` calls `end_edit(save=True)`; `ZQ` calls `end_edit(save=False)`.
- `:` calls `_prompt_line`; `wq` saves/exits and `q!` discards/exits; unknown editor commands set a non-fatal message.
- Popup mode continues through `_edit_popup` and never invokes Vim dispatch.

Add localized mode/status strings and show `INSERT`, `NORMAL`, `VISUAL`, or `V-LINE` in the editor header/status. Run Step 5 and all existing editor tests. Expected: PASS.

- [ ] **Step 7: Write failing `yy` and Visual selection yank tests**

```python
def test_vim_yy_copies_current_line(tmp_notes, monkeypatch):
    c = vim_editor_controller()
    c.note_lines = ["first", "second"]
    c.note_cy, c.note_cx, c.note_mode = 1, 2, "normal"
    copied = []
    monkeypatch.setattr(tui, "_copy_clipboard",
                        lambda text: (copied.append(text) or True, ""))
    tui._handle_vim_note_key(None, c, "y")
    tui._handle_vim_note_key(None, c, "y")
    assert copied == ["second\n"]


def test_vim_character_visual_yank_is_inclusive(tmp_notes, monkeypatch):
    c = vim_editor_controller()
    c.note_lines = ["alpha", "beta"]
    c.note_cy, c.note_cx, c.note_mode = 0, 2, "normal"
    copied = []
    monkeypatch.setattr(tui, "_copy_clipboard",
                        lambda text: (copied.append(text) or True, ""))
    tui._handle_vim_note_key(None, c, "v")
    tui._handle_vim_note_key(None, c, "l")
    tui._handle_vim_note_key(None, c, "l")
    tui._handle_vim_note_key(None, c, "y")
    assert copied == ["pha"]
    assert c.note_mode == "normal"


def test_vim_line_visual_yank_includes_complete_lines(tmp_notes, monkeypatch):
    c = vim_editor_controller()
    c.note_lines = ["alpha", "beta", "gamma"]
    c.note_cy, c.note_mode = 0, "normal"
    copied = []
    monkeypatch.setattr(tui, "_copy_clipboard",
                        lambda text: (copied.append(text) or True, ""))
    tui._handle_vim_note_key(None, c, "V")
    tui._handle_vim_note_key(None, c, "j")
    tui._handle_vim_note_key(None, c, "y")
    assert copied == ["alpha\nbeta\n"]
```

Add a multi-line character selection case from `(0, 3)` through `(1, 1)` expecting `"ha\nbe"`.

- [ ] **Step 8: Run yank tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'vim_yy or visual_yank'
```

Expected: no selection/yank behavior.

- [ ] **Step 9: Implement selection ranges, visible highlighting, and yank**

Store `note_anchor=(note_cy, note_cx)` on `v`/`V`. `note_selection_range` returns ordered anchor/cursor endpoints. Characterwise extraction is inclusive at both ends and joins crossed lines with `\n`; linewise extraction joins complete selected lines and appends a final newline.

On successful `_copy_clipboard`, set `note_mode="normal"`, clear anchor/pending state, and show localized copied status. On failure keep the selection and show the adapter error.

Add `_note_selected_spans(c) -> dict[int, tuple[int, int]]`, returning codepoint ranges per selected line. After drawing the editor pane, call `_highlight_note_selection`; convert codepoint prefixes to terminal cells with `_cell_width` and use `screen.stdscr.chgat(row, start_cell, max(1, length_cells), curses.A_REVERSE)` for visible selected spans. Catch `curses.error` so narrow panes remain safe.

Run Step 8 plus renderer/editor tests. Expected: PASS.

- [ ] **Step 10: Write failing Normal and Visual paste tests**

```python
def test_vim_p_and_P_paste_multiline_clipboard(tmp_notes, monkeypatch):
    c = vim_editor_controller()
    c.note_lines = ["abcd"]
    c.note_cy, c.note_cx, c.note_mode = 0, 1, "normal"
    monkeypatch.setattr(tui, "_read_clipboard", lambda: ("X\nY", ""))
    tui._handle_vim_note_key(None, c, "p")
    assert c.note_lines == ["abX", "Ycd"]

    c.note_lines = ["abcd"]
    c.note_cy, c.note_cx, c.note_mode = 0, 1, "normal"
    tui._handle_vim_note_key(None, c, "P")
    assert c.note_lines == ["aX", "Ybcd"]


def test_vim_visual_p_replaces_selection(tmp_notes, monkeypatch):
    c = vim_editor_controller()
    c.note_lines = ["abcdef"]
    c.note_cy, c.note_cx, c.note_mode = 0, 1, "normal"
    monkeypatch.setattr(tui, "_read_clipboard", lambda: ("XY", ""))
    tui._handle_vim_note_key(None, c, "v")
    tui._handle_vim_note_key(None, c, "l")
    tui._handle_vim_note_key(None, c, "l")
    tui._handle_vim_note_key(None, c, "p")
    assert c.note_lines == ["aXYef"]
    assert c.note_mode == "normal"


def test_vim_paste_failure_keeps_note_unchanged(tmp_notes, monkeypatch):
    c = vim_editor_controller()
    c.note_lines = ["unchanged"]
    c.note_mode = "normal"
    monkeypatch.setattr(tui, "_read_clipboard", lambda: (None, "clipboard unavailable"))
    tui._handle_vim_note_key(None, c, "p")
    assert c.note_lines == ["unchanged"]
    assert "unavailable" in c.message
```

- [ ] **Step 11: Run paste tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_tui2.py -k 'vim_p_and_P or visual_p or paste_failure'
```

Expected: no note paste behavior.

- [ ] **Step 12: Implement clipboard insertion/replacement**

Implement one text insertion helper that splits on `\n`, splices the first/last fragments into the surrounding line, inserts middle lines, and leaves the cursor at the end of pasted content. Normal `p` inserts at `min(len(line), note_cx + 1)` and `P` at `note_cx`.

For Visual `p`, delete the inclusive character selection (or complete selected lines for `V`) and insert clipboard content at the selection start. Empty clipboard text is a no-op with localized feedback. Mark successful mutation `note_dirty=True`, return to Normal mode, and clear selection state.

Run Step 11 and all note tests. Expected: PASS.

- [ ] **Step 13: Commit the task**

```bash
git add src/exeg/tui.py src/exeg/i18n.py tests/test_tui2.py
git commit -m "feat: add optional Vim note keybindings"
```

### Task 7: Bilingual Help Contract and Full Local Verification

**Files:**
- Modify: `src/exeg/tui.py:1241-1520`
- Modify: `tests/test_help_contract.py`
- Test: all Python and Node tests

**Interfaces:**
- Documents: `[`/`]`, NAV `Ctrl-U`/`Ctrl-D`, and `y` behavior in English and Simplified Chinese.

- [ ] **Step 1: Write the failing Help contract**

```python
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_help_documents_chapter_fast_nav_and_copy_keys(lang):
    text = "\n".join(line for line, _kind in tui.help_lines(lang))
    for token in ("[", "]", "Ctrl-U", "Ctrl-D", "y"):
        assert token in text
    if lang == "en":
        assert "previous chapter" in text and "next chapter" in text
        assert "five" in text and "copy" in text
    else:
        assert "上一章" in text and "下一章" in text
        assert "五项" in text and "复制" in text


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_help_documents_optional_vim_note_copy_paste(lang):
    text = "\n".join(line for line, _kind in tui.help_lines(lang))
    for token in ("yy", "v/V", "p/P", ":wq", ":q!", "ZZ", "ZQ"):
        assert token in text
    assert ("disabled by default" in text if lang == "en" else "默认关闭" in text)
    assert ("system clipboard" in text if lang == "en" else "系统剪贴板" in text)
```

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/test_help_contract.py -k 'chapter_fast_nav_and_copy'
```

Expected: missing chapter/copy/five-item documentation.

- [ ] **Step 3: Update both Help manuals**

Add to reading mode: `[` previous chapter, `]` next chapter, and `y` copy highlighted verse. Add to Navigator: `Ctrl-U / Ctrl-D` move five items and `y` copies the previewed highlighted verse. State that clipboard failure is reported in the status line.

In both Help manuals, document that Vim note keys are disabled by default and enabled in Settings, affect only inline editing, provide Insert/Normal/Visual modes, and support `yy`, `v/V` + `y`, `p/P`, `:wq`/`ZZ`, and `:q!`/`ZQ` through the system clipboard.

- [ ] **Step 4: Verify Help and focused TUI tests GREEN**

```bash
.venv/bin/pytest -q tests/test_help_contract.py tests/test_tui2.py
```

Expected: PASS.

- [ ] **Step 5: Run the complete Python suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass with no warnings or errors.

- [ ] **Step 6: Run Node launcher tests**

```bash
cd npm/scriexe && npm test
```

Expected: all launcher tests pass.

- [ ] **Step 7: Run source integrity checks**

```bash
git diff --check
git status --short
git diff -- src/exeg/tui.py src/exeg/i18n.py tests/test_tui2.py tests/test_help_contract.py
```

Expected: no whitespace errors; only planned TUI/i18n/test changes plus the user's pre-existing release/packaging work are present.

- [ ] **Step 8: Build the local native executable**

Use the repository's existing packaging flow and already staged core data:

```bash
.venv/bin/python packaging/build_core_data.py --source-root . --output build/core
.venv/bin/pyinstaller --clean --noconfirm packaging/scriexe.spec
```

Expected: `dist/scriexe` is produced successfully. Do not publish it.

- [ ] **Step 9: Smoke-test the native executable**

Run:

```bash
./dist/scriexe --version
./dist/scriexe passage "Isa 5:7" --versions cuvs
```

Create an isolated user-state directory and launch the built TUI in a 131-column terminal:

```bash
rm -rf /tmp/scriexe-tui-smoke
mkdir -p /tmp/scriexe-tui-smoke
EXEG_USER_ROOT=/tmp/scriexe-tui-smoke ./dist/scriexe
```

Verify this exact interaction sequence:

1. Confirm the title starts at `Matthew › 1 › v.1`.
2. Complete onboarding, press `o`, reduce the terminal height to 10 rows, and hold `j` until Restore is selected; confirm the selection stays visible.
3. Return to reading, press `]` and confirm `Matthew › 2 › v.1`; press `[` and confirm `Matthew › 1 › v.1`.
4. Open NAV, note the selected book, press `Ctrl-D` and confirm it advances five books; press `Ctrl-U` and confirm it returns five books.
5. Close NAV, press `y`, confirm the status reports copy success, and run `pbpaste` in another shell to confirm the copied reference and displayed versions.
6. Confirm Vim note keys are off in Settings. Enable them, edit a note, use `Esc`, `yy`, `v/V` + `y`, and `p/P`, verify clipboard contents with `pbpaste`, then use `:wq` and reopen the note to confirm it saved.
7. Navigate and commit Isaiah 5:7, quit, restart with the same `EXEG_USER_ROOT`, and confirm Isaiah 5:7 is restored.
8. At 131 columns confirm the CUVS row visibly contains `冤声。`.

Expected: all eight checks pass locally.

- [ ] **Step 10: Commit Help and final regression coverage**

```bash
git add src/exeg/tui.py src/exeg/i18n.py tests/test_tui2.py tests/test_help_contract.py
git commit -m "docs: document TUI reading shortcuts"
```

- [ ] **Step 11: Stop before publication**

Report exact test/build evidence, the native executable path, corpus-audit results, and any platform-only checks still requiring the user. Do not push, tag, create a release, or publish npm packages.
