# Chapter Hidden Scroll Anchor Design

**Date:** 2026-07-25
**Status:** Approved

## Goal

Make the first `j`/Down movement in Chapter scope visibly scroll the page, including when the real verse focus starts at a chapter boundary, while keeping Chapter focus entirely invisible and preserving the real verse focus for semantic actions.

## Root cause

Chapter currently reuses Window's absolute centered-focus calculation. Near the start of a chapter, centering clamps the scroll offset to zero. Moving the hidden real focus by one verse still leaves it inside the clamped half-pane region, so the first several `j`/Down presses change controller state without visibly moving the page. Window remains understandable because its moved focus is highlighted; Chapter has no visible focus, so the same behavior appears unresponsive.

## Behavior

- Chapter keeps a private visual scroll anchor independent from `Controller.focus`.
- On the first Chapter draw, the anchor is initialized with the current rendered focus row and the pane's vertical midpoint as its intended viewport position.
- The first draw still clamps naturally at the beginning or end of content and never inserts blank padding.
- After initialization, movement follows the rendered-row delta between the previous and current real focus positions. Consequently, the first successful `j`/Down at the top boundary advances the viewport immediately instead of waiting for the real focus to cross half the pane.
- `k`/Up reverses the same rendered-row delta.
- The delta uses rendered rows rather than a fixed terminal-line count, so multiple translations, RTL rows, and wrapping remain aligned.
- The visual anchor is reset when Chapter is entered again or when the rendered content, pane width, or pane height changes.
- Find navigation continues to use its own focused-hit positioning and does not reuse Chapter's movement anchor.

## Semantic focus

`Controller.focus` remains the source of truth for:

- copying a verse,
- verse and word notes,
- bookmarks,
- persisted reading position,
- title and navigation state.

The Chapter scroll anchor affects positioning only. It never becomes a verse selection and never changes semantic targets.

## Scope behavior

- Window scope retains absolute centered scrolling, visible focus styling, and dimmed surrounding context.
- Chapter scope retains no `KIND_FOCUS`, no no-color focus marker, and no dimming.
- Verse scope and non-reading panes retain keep-visible scrolling.

## Implementation boundary

- Add private Chapter scroll-anchor state to `Controller`.
- Keep `_draw_lines` as the shared renderer and boundary-clamping implementation.
- In `_draw_pane`, calculate the current rendered focus row with the existing line-to-row mapping.
- On Chapter anchor initialization, use centered drawing once and record the rendered focus row plus layout/content context.
- On later Chapter draws, add the rendered focus-row delta to the previous scroll offset, then draw without another absolute focus recenter.
- Clear the anchor while drawing other scopes or while contextual find positioning owns the pane focus.

No key-handler changes, synthetic blank rows, fixed scroll increments, or semantic-focus changes are required.

## Testing

Regression tests will verify:

- At a top boundary, Window remains at scroll zero after one small focus movement while Chapter immediately advances.
- Chapter follows the exact rendered-row delta for multi-line verse blocks.
- Chapter movement reverses on `k`/Up.
- Initial and reset draws clamp without blank padding.
- Changing pane geometry or rendered content resets the anchor safely.
- Window, Chapter, and Verse styling contracts remain unchanged.
- Chapter copy/note/bookmark targets remain tied to `Controller.focus`.

Final verification includes focused TUI tests, the complete Python suite, a fresh macOS arm64 frozen build, and smoke tests executed from the final archive.

## Superseded detail

This design refines `2026-07-25-chapter-scope-focus-scrolling-design.md`: Window and Chapter still share rendered focus-row measurement and boundary clamping, but Chapter now uses a persistent invisible delta-following anchor after its initial draw rather than repeating Window's absolute centering on every frame.
