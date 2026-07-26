# Responsive Status Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the TUI status bar as a responsive row-major grid whose shortcut, explanation, and separator columns align across rows, with a 30-cell minimum-width resize gate.

**Architecture:** Replace localized prose hints with structured `(shortcut, explanation)` items. A pure cell-aware layout function chooses the largest fitting column count, computes per-column shortcut and explanation widths across rows, distributes spare cells among separators, and returns display rows. The curses driver reserves those rows or shows a resize warning below the minimum width.

**Tech Stack:** Python 3.11, curses, pytest, PyInstaller; existing `_cell_width`, `_slice_cells`, `_put`, and translation helpers.

## Global Constraints

- Terminal layout measurements use terminal cells; wide CJK characters occupy two cells.
- Shortcut tokens such as `j/k`, `[/]`, `g/G`, `+/-`, and `:q` are never split.
- Shortcut starts, explanation starts, and `·` separators align vertically within each responsive grid column.
- An incomplete final row preserves established column widths but does not render unused columns.
- Minimum supported width is 30 cells: `NORMAL ·  j/k 移动 ·  [/] 章节`.
- Widths below 30 show a resize warning and automatically recover after `KEY_RESIZE`.
- Preserve the terminal lower-right-cell safety rule.
- Run all tests and rebuild `dist/scriexe/scriexe` before handoff.

---

### Task 1: Structured Status Data

**Files:**
- Modify: `src/exeg/tui.py`
- Modify: `src/exeg/i18n.py`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Produces: `StatusItem(shortcut: str, explanation: str)`
- Produces: `StatusModel(label: str, items: tuple[StatusItem, ...], message: str = "")`
- Produces: `_status_model(c: Controller) -> StatusModel`
- Consumes: existing controller mode state and `tr()` localization.

- [ ] **Step 1: Add failing structured-model tests**

Add tests asserting the Chinese NORMAL model begins with the exact structured items and keeps shortcut/explanation separate:

```python
def test_status_model_normal_zh_is_structured():
    c = make_controller()
    c.lang = "zh"
    c.nav_visible = False
    model = tui._status_model(c)
    assert model.label == "NORMAL"
    assert model.items[:4] == (
        tui.StatusItem("j/k", "移动"),
        tui.StatusItem("[/]", "章节"),
        tui.StatusItem("g/G", "首末节"),
        tui.StatusItem("V", "选择"),
    )
    assert tui.StatusItem(":q", "退出") in model.items


def test_status_model_normal_en_is_structured():
    c = make_controller()
    c.lang = "en"
    c.nav_visible = False
    model = tui._status_model(c)
    assert model.label == "NORMAL"
    assert model.items[0] == tui.StatusItem("j/k", "verse")
    assert tui.StatusItem(":q", "quit") in model.items
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/pytest tests/test_tui2.py -k status_model -v
```

Expected: failures because `StatusItem`, `StatusModel`, and `_status_model` do not exist.

- [ ] **Step 3: Add immutable status types and localized item data**

In `src/exeg/tui.py`, add:

```python
@dataclass(frozen=True)
class StatusItem:
    shortcut: str
    explanation: str


@dataclass(frozen=True)
class StatusModel:
    label: str
    items: tuple[StatusItem, ...]
    message: str = ""
```

Add `_status_model(c)` that returns structured items for NORMAL and preserves existing labels/hints for NAV, WORD, RESULT, SETTINGS, FIND, V-SEL, HELP, intro, and editor modes. Store localized explanations as item-level translations rather than parsing `normal_hint` strings. For Chinese NORMAL, use this ordered core:

```python
(
    StatusItem("j/k", "移动"),
    StatusItem("[/]", "章节"),
    StatusItem("g/G", "首末节"),
    StatusItem("V", "选择"),
    StatusItem("y", "复制"),
    StatusItem("z", "范围"),
    StatusItem("+/-", "窗口"),
    StatusItem("i", "笔记"),
    StatusItem("/", "查找"),
    StatusItem("b", "返回"),
    StatusItem("p", "设书签"),
    StatusItem("o", "设置"),
    StatusItem("?", "帮助"),
    StatusItem(":q", "退出"),
)
```

Use equivalent English explanations. Keep existing prose translation keys temporarily for backward-compatible help text; the status renderer consumes `_status_model()`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
.venv/bin/pytest tests/test_tui2.py -k status_model -v
```

Expected: all structured-model tests pass.

- [ ] **Step 5: Commit the structured-data change**

```bash
git add src/exeg/tui.py src/exeg/i18n.py tests/test_tui2.py
git commit -m "refactor: structure TUI status hints"
```

---

### Task 2: Responsive Cell-Aware Grid Layout

**Files:**
- Modify: `src/exeg/tui.py`
- Test: `tests/test_tui2.py`

**Interfaces:**
- Consumes: `StatusModel`, `StatusItem`, `_cell_width()`.
- Produces: `_layout_status_grid(model: StatusModel, width: int) -> list[str]`.
- Produces: `MIN_TUI_WIDTH = 30`.

- [ ] **Step 1: Add exact 52-cell and 64-cell failing tests**

Use the ten-item visual-contract model so the expected rows are unambiguous:

```python
def status_grid_fixture():
    return tui.StatusModel("NORMAL", (
        tui.StatusItem("j/k", "移动"),
        tui.StatusItem("[/]", "章节"),
        tui.StatusItem("g/G", "首末节"),
        tui.StatusItem("V", "选择"),
        tui.StatusItem("y", "复制"),
        tui.StatusItem("z", "范围"),
        tui.StatusItem("+/-", "窗口"),
        tui.StatusItem("o", "设置"),
        tui.StatusItem("?", "帮助"),
        tui.StatusItem(":q", "退出"),
    ))


def test_status_grid_52_cells_aligns_shortcuts_explanations_and_dots():
    rows = tui._layout_status_grid(status_grid_fixture(), 52)
    assert rows == [
        "NORMAL ·  j/k 移动 ·  [/] 章节 · g/G 首末节 · V 选择",
        "       ·  y   复制 ·  z   范围 · +/- 窗口   · o 设置",
        "       ·  ?   帮助 ·  :q  退出",
    ]
    assert tui._cell_width(rows[0]) == 52
    assert tui._cell_width(rows[1]) == 52


def test_status_grid_64_cells_aligns_shortcuts_explanations_and_dots():
    rows = tui._layout_status_grid(status_grid_fixture(), 64)
    assert rows == [
        "NORMAL ·  j/k 移动 ·  [/] 章节 ·  g/G 首末节 ·  V 选择 · y  复制",
        "       ·  z   范围 ·  +/- 窗口 ·  o   设置   ·  ? 帮助 · :q 退出",
    ]
    assert all(tui._cell_width(row) == 64 for row in rows)
```

Add a helper assertion that records cell positions of shortcut starts, explanation starts, and `·` separators, then verifies equal positions across rows where a column is populated.

- [ ] **Step 2: Run exact-layout tests and verify RED**

Run:

```bash
.venv/bin/pytest tests/test_tui2.py -k 'status_grid_52 or status_grid_64' -v
```

Expected: failures because `_layout_status_grid` does not exist or still performs prose wrapping.

- [ ] **Step 3: Implement responsive row-major layout**

Implement `_layout_status_grid` with this algorithm:

```python
MIN_TUI_WIDTH = 30


def _pad_cells(text: str, width: int) -> str:
    return text + " " * max(0, width - _cell_width(text))


def _layout_status_grid(model: StatusModel, width: int) -> list[str]:
    # Evaluate column counts from len(items) down to 1.
    # For each candidate C, assign item i to row i // C, column i % C.
    # For each column compute max shortcut width and max explanation width.
    # Cell width = shortcut_width + 1 + explanation_width.
    # Base row width = mode prefix + populated cells + minimum separators.
    # Reject a candidate if any complete row exceeds width.
    # Choose the largest accepted C.
    # Distribute spare cells of complete rows over inter-cell separator gaps,
    # left to right, while keeping separator positions shared across rows.
    # Format every populated cell with both shortcut and explanation padding.
    # Do not emit padding for nonexistent cells in the incomplete final row.
```

The mode prefix is `label + " ·  "`; continuation prefix is spaces matching `label` plus `" ·  "`. A minimum separator between item cells is `" · "`. Candidate acceptance must account for the maximum width needed at each grid column, not natural width of one row only.

For separator expansion, calculate the shared separator widths needed to make every complete row exactly `width` cells. Distribute remainder cells left-to-right so separator `·` cell positions remain identical across rows. The incomplete final row reuses these shared widths through its last populated column only.

- [ ] **Step 4: Add edge-case tests**

Add tests for:

```python
def test_status_grid_last_incomplete_row_keeps_explanation_alignment():
    rows = tui._layout_status_grid(status_grid_fixture(), 52)
    assert "?   帮助" in rows[-1]
    assert ":q  退出" in rows[-1]


def test_status_grid_uses_terminal_cells_for_cjk():
    rows = tui._layout_status_grid(status_grid_fixture(), 52)
    assert tui._cell_width(rows[0]) == 52


def test_status_grid_never_splits_shortcuts():
    for width in range(30, 81):
        joined = "\n".join(tui._layout_status_grid(status_grid_fixture(), width))
        for shortcut in ("j/k", "[/]", "g/G", "+/-", ":q"):
            assert shortcut in joined


def test_minimum_tui_width_contract():
    assert tui._cell_width("NORMAL ·  j/k 移动 ·  [/] 章节") == tui.MIN_TUI_WIDTH == 30
```

- [ ] **Step 5: Run grid tests and verify GREEN**

Run:

```bash
.venv/bin/pytest tests/test_tui2.py -k status_grid -v
```

Expected: all grid tests pass.

- [ ] **Step 6: Commit the layout engine**

```bash
git add src/exeg/tui.py tests/test_tui2.py
git commit -m "feat: align responsive status grid"
```

---

### Task 3: Curses Integration and Minimum-Width Gate

**Files:**
- Modify: `src/exeg/tui.py`
- Test: `tests/test_tui2.py`
- Test: `tests/test_help_contract.py`

**Interfaces:**
- Consumes: `_status_model()`, `_layout_status_grid()`, `MIN_TUI_WIDTH`.
- Produces: `_draw_status_rows(stdscr, rows: list[str], attr: int, h: int, w: int) -> int`.
- Produces: `_narrow_terminal_lines(lang: str, width: int) -> list[str]`.

- [ ] **Step 1: Add failing drawing and narrow-width tests**

```python
def test_narrow_terminal_gate_at_29_cells():
    assert tui._terminal_too_narrow(29)
    assert not tui._terminal_too_narrow(30)


def test_narrow_terminal_warning_is_compact():
    lines = tui._narrow_terminal_lines("zh", 29)
    assert any("窗口太窄" in line for line in lines)
    assert all(tui._cell_width(line) <= 29 for line in lines)


def test_draw_status_rows_uses_bottom_rows():
    win = FakeWin(24, 52)
    rows = tui._layout_status_grid(status_grid_fixture(), 52)
    used = tui._draw_status_rows(win, rows, 0, 24, 52)
    assert used == 3
    assert [y for y, _text in win.puts] == [21, 22, 23]
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
.venv/bin/pytest tests/test_tui2.py -k 'narrow_terminal or draw_status_rows' -v
```

Expected: failures because the gate and row drawer do not exist.

- [ ] **Step 3: Implement narrow warning and row drawing**

Add:

```python
def _terminal_too_narrow(width: int) -> bool:
    return width < MIN_TUI_WIDTH


def _narrow_terminal_lines(lang: str, width: int) -> list[str]:
    text = ("Terminal too narrow — resize to 30 columns"
            if lang == "en" else "窗口太窄 — 请调整到至少 30 列")
    return [_slice_cells(line, width) for line in _wrap_plain(text, max(1, width))]


def _draw_status_rows(stdscr, rows: list[str], attr: int,
                      h: int, w: int) -> int:
    usable = max(1, min(len(rows), h - 2))
    visible = rows[-usable:]
    for index, row in enumerate(visible):
        _put(stdscr, h - usable + index, 0, row, attr, w)
    return usable
```

Keep lower-right-cell behavior delegated to `_put`.

- [ ] **Step 4: Integrate into `run()`**

Before normal rendering in each loop iteration:

```python
h, w = screen.stdscr.getmaxyx()
if _terminal_too_narrow(w):
    screen.stdscr.erase()
    warning = _narrow_terminal_lines(controller.lang, w)
    # Draw warning safely in available rows.
    screen.stdscr.refresh()
    key = screen.stdscr.getch()
    if key in (ord("q"), 3):
        controller.running = False
    continue

status_rows_data = _layout_status_grid(_status_model(controller), w)
status_rows = min(len(status_rows_data), max(1, h - 2))
top, bottom = 1, h - status_rows
body_h = bottom - top
```

Replace prose `_status()` wrapping with `_draw_status_rows`. Recompute on every loop so `KEY_RESIZE` automatically selects a new column count and restores the interface after the gate clears.

- [ ] **Step 5: Run focused and full tests**

Run:

```bash
.venv/bin/pytest tests/test_tui2.py tests/test_help_contract.py -q
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit curses integration**

```bash
git add src/exeg/tui.py tests/test_tui2.py tests/test_help_contract.py
git commit -m "feat: gate narrow TUI and draw status grid"
```

---

### Task 4: Standalone Build and Manual Verification Handoff

**Files:**
- Verify: `packaging/build_core_data.py`
- Verify: `packaging/scriexe.spec`
- Build output: `dist/scriexe/` (gitignored)

**Interfaces:**
- Consumes: completed source and passing tests.
- Produces: rebuilt `dist/scriexe/scriexe`.

- [ ] **Step 1: Stage core data**

Run:

```bash
python packaging/build_core_data.py --output build/core
```

Expected: `build/core/data/corpus/` contains `cuvs`, `asv`, `sblgnt`, `wlc`, and `strongs`.

- [ ] **Step 2: Build the standalone application**

Run:

```bash
pyinstaller --clean --noconfirm packaging/scriexe.spec
```

Expected: build completes and creates `dist/scriexe/scriexe`.

- [ ] **Step 3: Smoke test**

Run:

```bash
dist/scriexe/scriexe --version
```

Expected: `0.2.0`.

- [ ] **Step 4: Hand off manual resize checks**

Ask the user to run:

```bash
dist/scriexe/scriexe
```

Manual checks:

1. Resize around 52 and 64 columns; separators, shortcuts, and explanations align vertically.
2. Confirm incomplete final rows preserve explanation alignment.
3. Resize to 29 columns; warning replaces the interface.
4. Resize back to 30+; interface restores automatically.
5. Confirm V-mode, note editor, and status hints still respond correctly.
