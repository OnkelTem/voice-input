# Voice Input — offline AI dictation daemon

Offline AI voice dictation daemon for Linux. Uses whisper.cpp with CUDA, xdotool for text injection.

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

Press and hold **Insert** to record, release to transcribe.

## Configuration

Config file at `~/.config/voice-input/config.toml` (all fields optional):

```toml
prompt = "медицинская диктовка: анамнез, диагноз, терапия"
model = "/projects/ai/whisper.cpp/models/ggml-small.bin"
binary = "/projects/ai/whisper.cpp/build/bin/whisper-cli"
key = "insert"
mode = "push-to-talk"
```

CLI flags override config file values:

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | `~/.config/voice-input/config.toml` | Config file path |
| `--model PATH` | `ggml-small.bin` | Whisper model path |
| `--binary PATH` | `whisper-cli` | Whisper binary path |
| `--prompt TEXT` | `""` | Initial prompt for transcription context |
| `--key NAME` | `insert` | Hotkey (insert, f1, f2, space, etc.) |
| `--mode NAME` | `push-to-talk` | Operating mode (push-to-talk or toggle) |

Example with prompt:
```bash
python voice_daemon.py --prompt "IT terminology: API, REST, database, deployment"
```

## Requirements

- whisper.cpp with CUDA at `/projects/ai/whisper.cpp/`
- xdotool (text injection via XTEST)
- libnotify-bin (desktop notifications)
- libportaudio2 (audio)
- Python 3.12+
