# Voice Input — offline AI dictation daemon

Offline AI voice dictation daemon for Linux with system tray indicator. Uses whisper.cpp with CUDA, xdotool for text injection.

## Setup

### Системные зависимости

```bash
sudo apt install xdotool libportaudio2 portaudio19-dev
```

Установите whisper-cli в систему:

```bash
cmake --install /projects/ai/whisper.cpp/build
```

### Установка voice-input

```bash
cd /projects/ai/voice-input
./install.sh
```

### Удаление

```bash
cd /projects/ai/voice-input
./uninstall.sh
```

## Usage

После установки команда `voice-input` доступна глобально. Просто запустите:

```bash
voice-input
```

Или через systemd-сервис (автоматически включён install.sh):

```bash
systemctl --user status voice-input
```

Press and hold **Right Shift** (по умолчанию, настраивается в конфиге) to record,
release to transcribe.

## Configuration

Config file at `~/.config/voice-input/config.toml`. Если файла нет — он создаётся
автоматически при первом запуске со всеми полями, закомментированными и с пояснениями.

CLI flags override config file values:

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | `~/.config/voice-input/config.toml` | Config file path |
| `--model PATH` | auto (ищет рядом с whisper-cli) | Whisper model path |
| `--binary PATH` | auto (ищет в $PATH) | Whisper binary path |
| `--prompt TEXT` | `""` | Initial prompt for transcription context |
| `--key NAME` | `insert` | Hotkey (shift_r, insert, f1, f2, space, etc.) |
| `--mode NAME` | `push-to-talk` | Operating mode (push-to-talk or toggle) |

## Requirements

- `whisper-cli` (из whisper.cpp) в $PATH
- `xdotool` — text injection
- `libportaudio2` — audio
- Python 3.12+
- PyQt5 — system tray indicator
- Pillow — tray icon generation
