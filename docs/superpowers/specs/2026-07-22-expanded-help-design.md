# Expanded TUI Help Design

## Goal

Turn the existing short shortcut list into a complete in-application manual without losing the useful command summary at the top.

## Language

Help follows the selected interface language:

- English interface: complete English help
- 中文界面：完整简体中文帮助

The two versions cover the same commands, behavior, examples, cautions, and output rules.

## Interaction

Help remains one scrollable overlay. Existing controls stay unchanged:

- `?` opens Help
- `j/k` or arrow keys scroll one display row
- `Enter` and `Ctrl-D` scroll down
- `Ctrl-U` scrolls up
- `q` or `Esc` closes Help

Long lines continue to use terminal-cell-aware wrapping. No new Help navigation mode is introduced.

## Content Structure

The existing shortcut summary remains first. Detailed sections follow in this order:

1. Navigator
2. Reading and the three scopes
3. Original-language word study
4. Notes and IME-safe editing
5. Find within the current preview
6. Corpus search and result navigation
7. Bookmark behavior
8. Settings and optional study-data download
9. Command reference
10. Export examples and file behavior
11. Exit/context behavior

## Command Detail Requirements

Every command entry explains:

- Syntax
- What state it changes
- Whether the change is session-only or persisted
- Required optional data where applicable
- At least one concrete example for commands whose arguments are not obvious

Commands documented:

- `:passage <ref>` and empty `:passage` clearing the study set
- `:versions <comma-list>`
- `:scope window|chapter|verse`
- `:word <Strong's number or lemma>`
- `:search <regex>`
- `:export <ref>`
- `:set` and all supported keys: `highlight`, `editor`, `window`, `notemark`
- `:setup`
- `:help`
- `:q`

## Export Documentation

Export receives expanded treatment because its current behavior is not obvious.

It explains that export:

- Accepts English or Chinese passage references
- Uses the currently effective translation list
- Compiles selected text plus attached book, chapter, verse, and word notes into Markdown
- Writes under the writable application root's `studies/` directory
- Uses `<slug>.md` for the first export
- Uses `<slug>.notes.md` when the first path already exists
- Reuses/overwrites the `.notes.md` path on further exports

Examples:

```text
:export Titus 1:1-4
→ studies/titus_1.1-4.md
```

```text
:export 彼前3:13-16
→ studies/1pet_3.13-16.md
```

The help does not claim that export formatting is mature beyond the implemented behavior.

## Presentation

The overlay uses visual hierarchy rather than one undifferentiated text block:

- Main title: header style
- Section headings: column-header style
- Commands/examples: emphasized or note style
- Explanations: normal style

The implementation stores localized help content separately from controller logic and renders it into the existing `(text, kind)` line model.

## Testing

Tests verify:

- Both languages contain all required detailed sections
- English and Chinese versions include both export examples and output paths
- Every executable TUI command appears in both languages
- Help rendering selects content by `Controller.lang`
- Shortcut summary remains before detailed sections
- Existing Help scrolling and close behavior remain unchanged
