# ADR 003: Toggle mode over push-to-talk

## Status
Superseded by ADR 006

## Context
Push-to-talk (hold key → record, release → transcribe) was the initial design. Implementing this reliably with global keyboard hooks proved difficult: key repeat events, race between press and release bindings, and inconsistent behavior across keyboard frameworks (sxhkd, pynput).

## Decision
Use toggle mode: press Insert once → recording starts, press Insert again → recording stops and transcription fires.

## Consequences
- **Positive:** Simple, deterministic state machine (recording vs idle)
- **Positive:** No key-repeat concerns; pynput handles single press events cleanly
- **Positive:** User controls duration explicitly — no accidental early cutoff
- **Negative:** Requires deliberate second press, slightly less fluid than hold-to-talk
