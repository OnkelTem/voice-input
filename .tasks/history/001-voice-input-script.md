# Voice Input Script

**Goal:** One Python daemon for offline AI voice dictation on Linux.

## Architecture

Single Python process (`voice_daemon.py`):
- `pynput` — global keyboard hook on Insert (toggle)
- `sounddevice` — record microphone to RAM buffer (16kHz mono)
- `whisper.cpp` — transcribe WAV from buffer
- `ydotool` — type transcribed text into active window

## How it works

1. Press Insert → start recording to in-memory buffer
2. Press Insert again → stop recording → write WAV to temp file
3. Run `whisper-cli` on temp file → get text
4. `ydotool type <text>` → text appears in active window
5. Delete temp WAV

## Dependencies

- `whisper.cpp` with CUDA + ggml-small.bin model
- Python packages: pynput, sounddevice, scipy, numpy
- System: ydotool, notify-send (libnotify-bin)

## Project structure

```
/projects/ai/voice-input/
├── pyproject.toml
├── voice_daemon.py
├── README.md
└── .venv/
```

## Usage

```
cd /projects/ai/voice-input
source .venv/bin/activate
python voice_daemon.py &
```

## Next steps

- Add autostart .desktop
- Test with mixed RU/EN speech
- Evaluate need for medium model
