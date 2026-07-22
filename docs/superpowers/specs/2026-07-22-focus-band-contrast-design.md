# Focus Band Contrast Design

## Goal

Increase the readability of scripture text inside the focused verse band.

## Design

Change the focused-content color pair from bold white text on a blue background to bold yellow text on a blue background. This applies to `KIND_FOCUS` only.

The following remain unchanged:

- Navigator selection colors
- Word-study token colors
- Search/result selection colors
- Minimal/no-color mode
- The blue focus-band background

## Testing

Add a regression test asserting that curses color pair 1 is initialized with a yellow foreground and blue background. Run the complete pytest suite.
