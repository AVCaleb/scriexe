# Chapter Scope Focus Scrolling Design

**Date:** 2026-07-25
**Status:** Approved

## Goal

Make Chapter scope use the same focus-following scroll position as Window scope while keeping the Chapter focus entirely invisible.

## Current behavior and root cause

Verse rendering already maintains a logical `focus_line` for both scopes. Chapter scope deliberately avoids `KIND_FOCUS`, focus markers, and context dimming. However, the pane-drawing layer enables centered focus scrolling only for Window scope, so Chapter scope merely keeps its logical focus visible instead of positioning it like Window scope.

## Behavior

- Window scope keeps its existing presentation: the focused verse is highlighted and surrounding context is dimmed.
- Chapter scope keeps its existing presentation: no focused-verse highlight, no no-color focus marker, and no dimming of other verses.
- Window and Chapter scopes feed their logical `focus_line` into the same centered scrolling algorithm.
- For a focus away from content boundaries, the focused verse is positioned near the vertical center of the pane.
- At the start or end of a chapter, scrolling clamps naturally to the available content. It does not add blank padding merely to force exact centering.
- Existing focus movement (`j/k`, `g/G`, and other reading navigation) continues to update the logical focus and therefore drives scrolling in both scopes.
- Verse scope and non-reading panes retain their existing scrolling behavior.

## Implementation boundary

Keep focus styling and focus positioning independent:

1. `_render_verse` continues to return the logical focused verse line in Chapter scope without assigning `KIND_FOCUS`.
2. `_draw_pane` enables centered focus scrolling when the active scope is either `window` or `chapter`.
3. `_draw_lines` remains the shared implementation for centering and boundary clamping.

No scope-policy framework or unrelated rendering refactor is needed.

## Testing

Regression tests will verify:

- Chapter scope emits neither `KIND_FOCUS` nor `KIND_DIM` while still returning its logical `focus_line`.
- Given identical content, pane size, and logical focus, Window and Chapter scopes calculate the same scroll offset.
- Middle focus positions are centered when possible.
- Start and end positions clamp without artificial blank rows.
- Window scope retains focused styling and dimmed context.
- Verse scope remains unaffected.

Run the focused TUI tests first, followed by the complete Python test suite and `git diff --check`.

## Superseded detail

This design preserves the no-highlight requirement in `2026-07-25-tui-search-word-rendering-design.md` while clarifying that Chapter and Window scopes must share the same centered focus-following scroll behavior.
