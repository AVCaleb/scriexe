# TUI Reading, Navigation, Persistence, and Rendering Design

**Date:** 2026-07-23
**Status:** Approved

## Goal

Repair seven reported scriexe TUI problems: keep the Settings selection visible in small terminals, add chapter navigation, restore the last committed reading position, start first-time users at Matthew 1:1, add five-item NAV movement, prevent wrapped Scripture from losing characters, and copy the highlighted verse to the system clipboard.

## Confirmed interaction design

- `[` opens the previous canonical chapter at verse 1.
- `]` opens the next canonical chapter at verse 1.
- Chapter movement crosses book boundaries. `[` at Genesis 1:1 and `]` at Revelation 22 remain at their respective canonical endpoints.
- In NAV, `Ctrl-U` moves five items up and `Ctrl-D` moves five items down, clamped to the active column. Their existing half-screen scrolling behavior remains unchanged outside NAV.
- `y` copies the highlighted verse reference and every currently displayed translation. In NAV it copies the previewed selection; in ordinary reading mode it copies the committed focus. It is unavailable in Help, Settings, Results, Word, onboarding, and the default note-editing keymap. When optional Vim note keys are enabled, `y` is reserved for note yank operations.
- A successful copy reports status in the TUI. A missing or failed platform clipboard command reports a non-fatal status message.

## Reading-position behavior

The persisted reading position is a structured metadata value containing OSIS book id, chapter, and verse. Only committed focus changes are saved; moving through NAV previews is not.

On startup:

1. If onboarding is incomplete, the controller starts at Matthew 1:1 and shows onboarding.
2. If onboarding is complete and a valid saved reading position exists, that position is restored.
3. If the saved value is missing or invalid, Matthew 1:1 is used.

Finishing onboarding leaves the reader at Matthew 1:1. Reading-position writes merge with existing metadata so `setup_done`, language, translations, and display preferences are preserved. Preference writes likewise preserve the reading position and onboarding state.

## Settings visibility

Settings rendering returns the logical line containing the selected item as its focus line. The existing pane drawing and wrapping code then scrolls that line into view whenever terminal height shrinks or terminal zoom reduces the number of visible rows. The same mapping technique is used for onboarding because it has the same selectable-list shape.

## Scripture rendering integrity

The CUVS source and normalized corpus both contain the final word in Isaiah 5:7; the loss occurs during terminal drawing. Wrapped rows are built using the full pane width, but `_put` currently clips every write to one column less. At a 131-column pane this consumes the row containing `声` and then omits that wide character while drawing, leaving only `。` on the continuation row.

The fix allows body rows to use the complete available width. Only a write that actually reaches the terminal's lower-right cell receives special handling for curses compatibility. This is a generic renderer fix and applies to Chinese, Hebrew, Greek, English, headings, notes, and status content rather than altering Scripture data.

A local corpus audit will compare all normalized CUVS verses with their parsed USFM sources and exercise rendered rows across representative terminal widths. No Scripture corpus content will be changed unless that audit independently finds a source-to-normalized mismatch.

## Clipboard architecture

A pure formatter gathers one single-verse reference through the existing display layer and emits:

1. `English reference · Chinese reference`
2. one line per effective displayed version as `Label  text`
3. any display-layer availability notices only as status feedback, not copied Scripture content

A small platform adapter sends UTF-8 text to:

- macOS: `pbcopy`
- Windows: `clip`
- Linux/Unix: first available of `wl-copy`, `xclip -selection clipboard`, or `xsel --clipboard --input`

The adapter uses subprocess standard input without invoking a shell. Tests inject command discovery and process execution; they do not modify the developer's real clipboard.

The same adapter can read clipboard text for optional Vim paste operations. It uses `pbpaste` on macOS, PowerShell `Get-Clipboard -Raw` on Windows, and the first available of `wl-paste --no-newline`, `xclip -selection clipboard -o`, or `xsel --clipboard --output` on Linux/Unix.

## Optional Vim note keymap

Settings adds a persisted `vim_keys` checkbox that is off by default. A note directly below it explains in English or Chinese that the mode provides Vim-style navigation, selection, system-clipboard copy, and paste for users who prefer that workflow. It affects only the inline note editor; the terminal-input popup editor retains its existing plain-input behavior.

With `vim_keys` disabled, note editing is unchanged: typing inserts text, Esc saves and exits, and Ctrl-C discards.

With `vim_keys` enabled:

- editing starts in Insert mode
- Esc changes Insert or Visual mode to Normal mode
- `i` and `a` enter Insert mode
- `h/j/k/l`, arrow keys, `0`, `$`, `gg`, and `G` move the cursor
- `yy` yanks the current line to the system clipboard
- `v` starts characterwise Visual mode and `V` starts linewise Visual mode
- `y` in Visual mode yanks the selected text to the system clipboard and returns to Normal mode
- `p`/`P` paste system clipboard text after/before the cursor in Normal mode; Visual `p` replaces the selection
- `:wq` or `ZZ` saves and exits
- `:q!` or `ZQ` discards and exits

This is a focused Vim-style note keymap, not an attempt to embed or emulate all of Vim. Clipboard failures remain non-fatal and are shown in the status line.

## Component changes

- `src/exeg/tui.py`
  - default and restored reading position
  - metadata-preserving persistence
  - previous/next chapter actions
  - five-item NAV movement
  - Settings/onboarding selected-line focus
  - verse-copy formatting, bidirectional platform clipboard adapter, key handling, status messages
  - optional Vim note Normal/Insert/Visual state and yank/paste operations
  - full-width-safe drawing
  - bilingual Help updates
- `src/exeg/i18n.py`
  - clipboard messages, Vim setting explanation, and editor-mode status strings
- `tests/test_tui2.py`
  - controller, key routing, rendering, clipboard, Vim note editing, persistence, and narrow-height regressions
- `tests/test_help_contract.py`
  - new documented key contracts where applicable

No packaging dependency is added.

## Error handling

- Invalid persisted book/chapter/verse values are ignored and replaced by Matthew 1:1.
- Chapter movement clamps at the canonical beginning and end.
- Empty NAV columns remain safe during five-item movement.
- Clipboard command absence, non-zero exit, or OS errors do not terminate curses; the status line explains that copying or pasting failed.
- Empty clipboard paste is a no-op with status feedback.
- Popup note editing ignores `vim_keys` and preserves ordinary text entry.
- Display-layer unavailable-version notices do not prevent installed versions from being copied.

## Test and local verification strategy

Development follows red-green-refactor. Regression tests first demonstrate each current failure:

- selected Settings item has an incorrect fixed focus line
- no chapter movement keys exist
- controller always starts at 1 Peter 3:18
- onboarding does not start at Matthew 1:1
- NAV ignores five-item movement
- a 131-column draw drops `声` from Isaiah 5:7
- no focused-verse copy action exists
- no persisted opt-in Vim note keymap, selection yank, or clipboard paste exists

After focused tests pass, verification includes:

1. full Python test suite
2. Node launcher test suite
3. Git whitespace check
4. all-book CUVS source/normalized corpus audit
5. local PyInstaller/native build and executable smoke test where supported on this macOS host
6. manual pseudo-terminal checks for Settings scrolling, chapter keys, NAV movement, persistence across restart, verse copy, and Isaiah 5:7 rendering

Work stops before publishing packages, creating a release, or pushing release tags.
