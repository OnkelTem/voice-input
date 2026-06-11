# Voice Input — offline AI dictation daemon

Offline AI voice dictation daemon for Linux with system tray indicator. Uses whisper.cpp with CUDA, xdotool for text injection.

## Setup

```bash
cd /projects/ai/voice-input
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
source .venv/bin/activate
python voice_daemon.py
```

Press and hold **Right Shift** to record (300ms arm delay prevents accidental taps), release to transcribe.

## Configuration

Config file at `~/.config/voice-input/config.toml` (all fields optional):

```toml
prompt = "медицинская диктовка: анамнез, диагноз, терапия"
model = "/projects/ai/whisper.cpp/models/ggml-small.bin"
binary = "/projects/ai/whisper.cpp/build/bin/whisper-cli"
key = "shift_r"
mode = "push-to-talk"
```

CLI flags override config file values:

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | `~/.config/voice-input/config.toml` | Config file path |
| `--model PATH` | `ggml-small.bin` | Whisper model path |
| `--binary PATH` | `whisper-cli` | Whisper binary path |
| `--prompt TEXT` | `""` | Initial prompt for transcription context |
| `--key NAME` | `shift_r` | Hotkey (insert, f1, f2, space, etc.) |
| `--mode NAME` | `push-to-talk` | Operating mode (push-to-talk or toggle) |

Example with prompt:
```bash
python voice_daemon.py --prompt "IT terminology: API, REST, database, deployment"
```

During recording audio accumulates; transcription runs as a single block when the key is released.
A short beep plays when recording begins.

## Requirements

- whisper.cpp with CUDA at `/projects/ai/whisper.cpp/`
- xdotool (text injection via XTEST)
- libportaudio2 (audio)
- Python 3.12+
- PyQt5 — system tray indicator
- Pillow — tray icon generation
