# ADR 005: ydotool for text input

Superseded — actual implementation uses `xdotool` (see ADR 004)

## Status
Accepted

## Context
The daemon needs to type transcribed text into the currently focused application. Options: `xdotool` (X11 only), `ydotool` (generic Linux input), `wtype` (Wayland only), `xclip` / `wl-clipboard` + Ctrl+V.

## Decision
Use `ydotool type` to simulate keystrokes.

## Consequences
- **Positive:** Works on both X11 and Wayland without modification
- **Positive:** Does not require the `ydotool` daemon (can use `ydotool` as standalone)
- **Positive:** Simple API — just `ydotool type "text"`
- **Negative:** Requires `ydotool` to be installed system-wide via apt
- **Negative:** May not handle very long text well (no chunking implemented)
