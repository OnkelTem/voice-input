# ADR 001: Python daemon over shell scripts

Superseded by ADR 004 (xdotool) and ADR 008 (in-process whisper.cpp via cffi)

## Status
Accepted

## Context
Initial implementation used separate shell scripts orchestrated by `sxhkd`. Each key press spawned a process chain: `sxhkd` → shell script → `pw-record` → `whisper-cli` → `ydotool`. This led to race conditions, duplicate processes, corrupted temp files, and general fragility.

## Decision
Use a single long-running Python daemon (`voice_daemon.py`) that:
- Listens for global keyboard events via `pynput`
- Records audio into an in-memory buffer via `sounddevice`
- Transcribes via `whisper-cli` subprocess
- Types output via `ydotool`

All orchestration lives in one process with one event loop.

## Consequences
- **Positive:** No race conditions, no duplicate processes, in-memory audio (no temp file corruption), single source of truth for state
- **Positive:** Easy to extend (language detection, key remapping, audio feedback)
- **Negative:** Requires Python runtime and 3 additional packages
