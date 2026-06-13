# 011 — Project icon (SVG)

## Goal

Create a vector application icon for the Voice Input project, saved in the
repository so it can be used in `.desktop` entries, window decorations, and
future packaging.

## Changes

### A. `icons/voice-input.svg`

48×48 SVG microphone icon in the project's signature blue `#1976D2`.

- Rounded-rectangle microphone body with three horizontal grille lines
- Vertical stem and wide base
- Transparent background
- Stylistically consistent with the existing Pillow-generated tray icons

### B. Future use

Once packaged, the icon can be installed to
`~/.local/share/icons/hicolor/scalable/apps/voice-input.svg` and referenced by a
`.desktop` entry with `Icon=voice-input`.

## Criteria

- [ ] `icons/voice-input.svg` exists and is a valid SVG
- [ ] Design matches the existing microphone style from `generate_icons()`
- [ ] Icon uses `#1976D2` as the primary color
- [ ] ViewBox is `0 0 48 48`
- [ ] Task file is created at `.tasks/active/011-icon.md`
