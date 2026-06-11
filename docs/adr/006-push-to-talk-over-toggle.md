# ADR 006: Push-to-talk over toggle mode

## Status
Accepted (supersedes ADR 003)

## Context
The original daemon used toggle mode (press once to start, press again to stop).
This was chosen in ADR 003 because push-to-talk was considered unreliable with
global keyboard hooks. However, pynput's `Listener` natively supports both
`on_press` and `on_release` callbacks, making push-to-talk straightforward:
start recording on press, stop + transcribe on release.

Additionally, toggle mode requires two deliberate actions (press-start,
press-stop), which is less fluid for dictation. Push-to-talk maps naturally
to the metaphor of "holding a push-to-talk button."

Two practical concerns were addressed:
1. **Accidental taps** — a 300ms arming timer prevents recording on quick
   inadvertent presses. If the key is released before the timer fires, no
   recording starts.
2. **Very short recordings** — if the recording lasts less than 2 seconds,
   transcription is skipped and a "Cancelled" notification is shown.

## Decision
Switch to push-to-talk as the default (and currently only) mode.
The code structure supports a future `mode = "toggle"` option.

## Consequences
- **Positive:** More intuitive — hold to record, release to transcribe
- **Positive:** Single-action recording; no second press needed
- **Positive:** 300ms arm timer filters out accidental taps
- **Positive:** 2-second minimum prevents wasted transcription on short bursts
- **Negative:** Requires holding the key for the entire recording duration
- **Negative:** Slightly more complex state machine (IDLE → ARMING → RECORDING)
