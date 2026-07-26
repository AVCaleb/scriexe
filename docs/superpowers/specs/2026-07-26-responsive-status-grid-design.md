# Responsive Status Grid Design

**Date:** 2026-07-26

## Goal

Replace the bottom status hint's prose wrapping with a responsive terminal grid. Shortcut commands, explanations, and separators remain vertically aligned across rows. The layout adapts to terminal width, and the normal interface is gated behind a minimum usable width.

## Visual contract

At a 52-cell content width, the Chinese NORMAL status should follow this structure:

```text
NORMAL ·  j/k 移动 ·  [/] 章节 · g/G 首末节 · V 选择
       ·  y   复制 ·  z   范围 · +/- 窗口   · o 设置
       ·  ?   帮助 ·  :q  退出
```

At a 64-cell content width:

```text
NORMAL ·  j/k 移动 ·  [/] 章节 ·  g/G 首末节 ·  V 选择 ·  y 复制
       ·  z   范围 ·  +/- 窗口 ·  o   设置   ·  ? 帮助 · :q 退出
```

The examples specify alignment, not literal ASCII character counts. All measurements use terminal cell widths; wide CJK characters occupy two cells.

## Layout model

The status is structured data rather than one preformatted string:

- A mode label, such as `NORMAL`, `NAV`, `WORD`, `RESULT`, `FIND`, `V-SEL`, or `INSERT`.
- An ordered list of hint items.
- Each hint item has two fields:
  - shortcut/command, such as `j/k`, `[/]`, `g/G`, `+/-`, or `:q`;
  - explanation, such as `移动`, `章节`, `首末节`, `窗口`, or `退出`.
- Messages remain a separate optional status element rather than being parsed back out of display text.

The renderer chooses the largest number of item columns that fits the terminal width, then fills items row-major.

For each responsive grid column, it computes across every row occupying that column:

1. maximum shortcut cell width;
2. maximum explanation cell width;
3. resulting item-cell width;
4. separator position.

Each item is rendered as:

```text
shortcut padded to column shortcut width
+ one separating space
+ explanation padded to column explanation width
```

This aligns shortcut starts, explanation starts, and following `·` separators vertically. Alignment remains active on an incomplete final row; only unused item columns on its right remain blank.

## Mode column

The mode label occupies a fixed left column. The first row prints the label followed by ` · `. Continuation rows print spaces in place of the label and retain the aligned `·`:

```text
NORMAL · ...
       · ...
       · ...
```

The mode-column width is based on the active mode label's terminal-cell width. It is independent of item-grid column widths.

## Width selection

The renderer evaluates candidate item-column counts from largest to smallest. A candidate is accepted only if all computed columns, separators, and the mode column fit the available terminal width.

The chosen candidate maximizes the number of columns per row. This minimizes row count and avoids unnecessary right-side blank space. The incomplete final row uses the established grid but does not pad through nonexistent columns.

Individual command tokens are never split. If an explanation alone exceeds its computed cell width, it may wrap at ordinary word boundaries; command tokens such as `j/k`, `[/]`, `g/G`, `+/-`, and `:q` remain intact.

## Minimum terminal size

The minimum usable width is the terminal-cell width required to render this complete row:

```text
NORMAL ·  j/k 移动 ·  [/] 章节
```

For the current Chinese labels this is 30 terminal cells. The implementation should derive or assert the minimum from structured content rather than rely on Python character count.

A curses application cannot portably prevent its host terminal from becoming smaller. When the terminal width is below the minimum:

1. suspend normal title/content/status rendering;
2. show a compact resize warning;
3. keep processing resize events;
4. automatically restore the normal interface when the terminal becomes usable again;
5. continue to permit a safe quit key where possible.

The warning must itself degrade safely if the terminal is extremely small.

## Other status modes

The same structured grid renderer applies to NORMAL, NAV, WORD, RESULT, FIND, V-SEL, editor modes, Settings, Help, and first-run status where useful. Short statuses remain a single row. Status messages may precede the grid or use a dedicated row, but must not destroy item-column alignment.

No status mode should be parsed from a localized display string. English and Chinese provide structured shortcut/explanation pairs so translated explanation widths are measured correctly.

## Main-pane integration

Before drawing the main pane, the run loop computes the status grid rows for the current width. The status row count is subtracted from the main body height. The grid is then drawn in the reserved bottom rows.

A resize triggers a fresh layout calculation. No persistent status-grid scroll state is needed.

## Error and edge handling

- Use terminal cell widths for all layout decisions.
- Preserve at least one body row whenever the terminal meets the minimum supported dimensions.
- Never write into the terminal's unsafe lower-right cell.
- If an unusually long localized explanation cannot fit a candidate grid, reduce the item-column count.
- If even one item cannot fit at the minimum width, show the narrow-terminal warning rather than clip commands.

## Testing

Pure tests should cover:

- exact separator, shortcut, and explanation start columns for the 52-cell example;
- exact alignment for the 64-cell example;
- incomplete final-row alignment;
- English and Chinese terminal-cell measurement;
- dynamic column-count changes on resize;
- command tokens remaining intact;
- minimum-width boundary: 30 accepted, 29 gated;
- resize warning activation and recovery;
- main-pane body height reduction by status row count;
- safe handling of extremely short/narrow terminals.

After automated tests, rebuild the standalone application and manually verify resizing behavior in `dist/scriexe/scriexe`.
