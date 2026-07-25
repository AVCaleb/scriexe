# TUI Search, Word Study, and Rendering Refinements

**Date:** 2026-07-25
**Status:** Approved by the user's explicit behavior list and prior instruction to proceed without repeated confirmation

## Goal

Make note yanking, search navigation, reading scopes, word study, translation wrapping, references, and help text behave predictably without changing Scripture or original-language corpus data.

## Note editing

When optional Vim note keys are enabled, `i` from reading or word study opens the inline note editor in Normal mode. The ordinary non-Vim editor continues to open ready for text entry.

The note command `:q` exits only when the note buffer is unchanged. If it has changed, the editor remains open and reports that `:wq` saves and `:q!` discards. This lets a reader open a note, yank text, and leave with `:q` without writing the note. Existing `:wq`, `:q!`, `ZZ`, and `ZQ` behavior remains.

## Contextual controls

The normal status line describes bookmark keys separately: `p` sets or replaces the bookmark and `b` returns to it. It also advertises reading `g/G` as first/last verse navigation.

After `/` finds preview hits, the status line switches to a FIND-specific hint. `n` moves to the next hit, `N` to the previous hit, Enter accepts the current viewport and clears find highlighting, and Esc exits find. Help in both languages documents those actual controls.

NAV continues to use Ctrl-U/Ctrl-D for exactly five items. Both the summary and detailed Help pages state the numeric five-item step.

## Search ordering

Corpus search results are sorted by:

1. canonical book order,
2. chapter,
3. verse,
4. the user's requested translation order.

Thus all matching translations for one verse remain together before the next canonical verse. The ordering is implemented in the shared search layer so CLI and TUI results agree.

## Reading scopes and references

Window scope continues to emphasize the focused verse and dim its surrounding context. Chapter scope tracks the current verse for automatic scrolling and `j/k` movement but applies no focus highlight or no-color focus marker. Verse scope remains focused.

Visible verse and word-study headings use only the active interface language: English book names in English mode and Chinese abbreviations in Chinese mode. The copied verse heading follows the same rule. The title and bookmark/copy feedback use the same localized reference helper where applicable.

In ordinary reading, `g` jumps to the first verse and `G` to the last verse of the current study set. Without a temporary study set, those are the first and last verses of the current chapter.

## Word study

Word-study `j/k` changes the selected occurrence and returns that occurrence's logical line as the render focus. Existing scrolling therefore keeps the selected occurrence visible, including for very common words with thousands of occurrences. Enter opens the selected occurrence; Esc/h returns.

Strong's glosses are labeled as sourced from the OpenScriptures Strong's dictionaries. No lexical content is generated or changed.

## Translation wrapping

Translation rows continue to use one fixed label column. Wrapped LTR translations, including the seven-cell `Vulgate` label, use a hanging indent equal to the body start column. Wrapped WLC rows print the `WLC` label only on the first visual row; continuation rows preserve right-aligned Hebrew in the same body area without repeating the label.

The apparent WLC/KJV duplication is treated as a rendering issue. Corpus rows are not modified.

## Testing

Tests will cover:

- Vim Normal entry and clean/dirty `:q`
- separate bookmark hints and contextual FIND hints
- `/` navigation with `n/N`
- canonical-then-translation search ordering
- chapter scope without focus styling while retaining focus line
- five-item NAV Help and reading `g/G`
- word occurrence focus following `j/k`
- Strong's source annotation
- one label per wrapped translation and Vulgate hanging indentation
- language-specific headings and copied references

Final verification includes the full Python and Node suites, representative-width renderer audits, a frozen native build, and tmux TUI smoke tests. Work stops before pushing or publishing.
