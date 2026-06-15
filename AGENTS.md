# Voice Input

Python package (`voice_input/`) for offline AI voice dictation on Linux.

## Quick start

```bash
cd /projects/ai/voice-input
make
source .venv/bin/activate
python -m voice_input.voice_daemon
```

## Architecture

- **Push-to-talk**: Hold INSERT (default, configurable) to record, release to transcribe. A 50ms arm timer prevents accidental taps; recordings under 2 seconds are cancelled.
- **Audio**: `sounddevice` captures 16 kHz mono int16 into in-memory NumPy buffer; WAV written only when `save_recordings` is enabled — numpy array passed directly to `WhisperModel.transcribe()`.
- **Transcription**: In-process whisper.cpp via cffi (`whisper_model.py`). Loads `libwhisper.so.1` through a thin C helper (`whisper_helper.c` → `whisper_helper.so`) that accepts `whisper_full_params*` by pointer, avoiding cffi struct-by-value ABI mismatches. `whisper_full_default_params_by_ref()` provides a properly laid-out heap struct. Model loads once at startup, context accumulates via `n_max_text_ctx`. `WhisperModel.transcribe()` takes numpy array directly and normalises int16 → float32.
- **Language**: Auto-detect.
- **Text output**: `xdotool type` types into active window.
- **Tray icon**: PyQt5 `QSystemTrayIcon` shows state (idle/recording/transcribing) with three SVG icons (gray/red/blue) loaded from `voice_input/static/`. Context menu: Quit.
- **Start beep**: 1000 Hz sine wave (120ms, 20% amplitude) WAV file loaded from `voice_input/static/`, played via `paplay` before the recording stream opens.
- **Save recordings**: When `save_recordings` is enabled in config, each audio file and its transcription text are saved to `~/.voice-input/recordings/` for later quality analysis.
- **Конфигурация**: секция `[whisper]` в `config.toml` позволяет настраивать параметры whisper.cpp (температура, язык, VAD и т.д.). Дефолтный конфиг — `voice_input/templates/config.toml`, копируется в `~/.config/voice-input/` при первом запуске.
- **Static assets**: Иконки (SVG) и звук (WAV) генерируются скриптами из `scripts/` через `make static`. Не требуют Pillow или NumPy для генерации.

## External dependencies (system-level)

- `xdotool` — text injection (via XTEST)
- `libportaudio2` — audio via `sounddevice`
- `paplay` (pulseaudio-utils) — start beep playback
- `whisper.cpp` with CUDA, built at `/projects/ai/whisper.cpp/`

## Python dependencies

- `PyQt5` — system tray indicator
- `pynput` — keyboard listener
- `sounddevice` — audio capture
- `scipy` — WAV file I/O
- `numpy` — audio buffer manipulation
- `cffi` — whisper.cpp binding via `whisper_helper.so`
- `python-xlib` — X11 key state polling

## Design docs

Architecture Decision Records in `docs/adr/`:
001 — Python daemon over shell scripts
002 — whisper.cpp over Python whisper
003 — Toggle mode over push-to-talk (superseded by ADR 006)
004 — pynput+sounddevice over sxhkd+pw-record
005 — xdotool for text input
006 — Push-to-talk over toggle mode
007 — VAD + incremental transcription (superseded — reverted in task 005)
008 — In-process whisper.cpp через cffi
