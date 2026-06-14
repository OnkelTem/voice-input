# ADR 004: pynput + sounddevice over sxhkd + pw-record

## Status
Accepted

## Context
Initial stack: `sxhkd` (keyboard daemon) → shell script → `pw-record` (PipeWire recording). Each key event spawned a new process. This caused race conditions, duplicate pw-record instances, and corrupted audio files when multiple processes wrote to the same path.

## Decision
Replace with Python-native libraries:
- `pynput` for global keyboard hook (replaces `sxhkd`)
- `sounddevice` for audio capture directly into a NumPy buffer (replaces `pw-record` + temp WAV)

## Consequences
- **Positive:** Single process, no IPC, no cleanup logic for stale processes
- **Positive:** Audio buffer lives entirely in RAM; WAV file written only once at the end
- **Positive:** Minimal dependency on PulseAudio CLI tools (only `paplay` for start beep)
- **Negative:** `pynput` may require `python3-xlib` or similar on some X11 setups
- **Negative:** `sounddevice` uses PortAudio internally — may need `libportaudio2` installed
