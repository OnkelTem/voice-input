# Voice Input

Single Python daemon (`voice_daemon.py`) for offline AI voice dictation on Linux.

## Quick start

```bash
cd /projects/ai/voice-input
source .venv/bin/activate
python voice_daemon.py
```

## Architecture

- **Push-to-talk**: Hold Right Shift to record, release to transcribe. A 50ms arm timer prevents accidental taps; recordings under 2 seconds are cancelled.
- **Audio**: `sounddevice` captures 16 kHz mono into in-memory NumPy buffer; WAV written to temp file only at transcription via `scipy.io.wavfile.write`.
- **Transcription**: `whisper-cli` subprocess — hardcoded paths:
  - Binary: `/projects/ai/whisper.cpp/build/bin/whisper-cli`
  - Model: `/projects/ai/whisper.cpp/models/ggml-small.bin`
- **Language**: Auto-detect (`-l auto`).
- **Text output**: `xdotool type` types into active window.
- **Tray icon**: PyQt5 `QSystemTrayIcon` shows state (idle/recording/transcribing) with three Pillow-generated microphone icons (gray/red/blue). A `QTimer(200ms)` polls a `ctypes.c_int` shared with pynput callbacks. Context menu: Quit.
- **Start beep**: 1000 Hz sine wave (120ms, 20% amplitude) generated with numpy, played via `paplay` before the recording stream opens.
- **Save recordings**: When `save_recordings` is enabled in config, each audio file and its transcription text are saved to `~/.voice-input/recordings/` for later quality analysis.

## External dependencies (system-level)

- `xdotool` — text injection (via XTEST)
- `libportaudio2` — audio via `sounddevice`
- `whisper.cpp` with CUDA, built at `/projects/ai/whisper.cpp/`

## Python dependencies

- `PyQt5` — system tray indicator
- `Pillow` — tray icon generation (48×48 RGBA)
- `pynput` — keyboard listener
- `sounddevice` — audio capture
- `scipy` — WAV file I/O
- `numpy` — audio buffer manipulation

## Design docs

Architecture Decision Records in `docs/adr/`:
001 — Python daemon over shell scripts
002 — whisper.cpp over Python whisper
003 — Toggle mode over push-to-talk (superseded by ADR 006)
004 — pynput+sounddevice over sxhkd+pw-record
005 — xdotool for text input
006 — Push-to-talk over toggle mode
007 — VAD + incremental transcription (superseded — reverted in task 005)
