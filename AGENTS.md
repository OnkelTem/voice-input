# Voice Input

Single Python daemon (`voice_daemon.py`) for offline AI voice dictation on Linux.

## Quick start

```bash
cd /projects/ai/voice-input
source .venv/bin/activate
python voice_daemon.py
```

## Architecture

- **Push-to-talk**: Hold Insert to record, release to transcribe. A 300ms arm timer prevents accidental taps; recordings under 2 seconds are cancelled.
- **Audio**: `sounddevice` captures 16 kHz mono into in-memory NumPy buffer; WAV written to temp file only at transcription via `scipy.io.wavfile.write`.
- **Transcription**: `whisper-cli` subprocess — hardcoded paths:
  - Binary: `/projects/ai/whisper.cpp/build/bin/whisper-cli`
  - Model: `/projects/ai/whisper.cpp/models/ggml-small.bin`
- **Language**: Auto-detect (`-l auto`).
- **Text output**: `xdotool type` types into active window.
- **VAD**: Энергетический детектор (RMS) прямо в callback sounddevice. При паузе > `vad_silence_ms` сегмент уходит в `queue.Queue`; фоновый поток транскрибирует инкрементально. Флаг `SPEECH_ACTIVE` предотвращает сплиты тишины после речи.

## External dependencies (system-level)

- `xdotool` — text injection (via XTEST)
- `libnotify-bin` — desktop notifications (`notify-send`)
- `libportaudio2` — audio via `sounddevice`
- `whisper.cpp` with CUDA, built at `/projects/ai/whisper.cpp/`

## Design docs

Architecture Decision Records in `docs/adr/`:
001 — Python daemon over shell scripts
002 — whisper.cpp over Python whisper
003 — Toggle mode over push-to-talk (superseded by ADR 006)
004 — pynput+sounddevice over sxhkd+pw-record
005 — xdotool for text input
006 — Push-to-talk over toggle mode
