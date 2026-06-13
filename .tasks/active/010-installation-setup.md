# 010 — Installation & setup improvements

Сделать проект устанавливаемым через pipx, добавить install.sh/uninstall.sh,
исправить systemd-сервис, настроить автоопределение whisper-cli в $PATH.

## Изменения

### A. `pyproject.toml` — build system + entry point

```toml
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project.scripts]
voice-input = "voice_daemon:main"
```

### B. `voice_daemon.py` — поиск whisper-cli в $PATH

- В `load_config()` / `build_config()`: если `binary` не задан в конфиге и не передан
  через `--binary`, искать `whisper-cli` через `shutil.which("whisper-cli")`.
- Если не нашли — оставить старый fallback `/projects/ai/whisper.cpp/build/bin/whisper-cli`.
- Модель: сначала из конфига/флага, потом искать `../models/ggml-small.bin` относительно
  найденного бинарника, потом старый fallback `/projects/ai/whisper.cpp/models/ggml-small.bin`.

### C. `voice_daemon.py` — создание директорий и дефолтного конфига

В `main()`:

1. `os.makedirs(os.path.expanduser("~/.config/voice-input"), exist_ok=True)`
2. Если `~/.config/voice-input/config.toml` не существует — записать файл со всеми
   полями по умолчанию, каждое закомментировано, с пояснениями.
3. `os.makedirs(CFG["recordings_dir"], exist_ok=True)` если `save_recordings`

Дефолтный конфиг-файл:
```toml
# Voice Input configuration
# Uncomment and modify values as needed.

# Transcription context prompt
# prompt = ""

# Path to whisper-cli binary
# binary = ""

# Path to whisper model file
# model = ""

# Hotkey: shift_r, insert, f1, f2, space, etc.
# key = "insert"

# Operating mode: "push-to-talk" or "toggle"
# mode = "push-to-talk"

# Save recordings for quality analysis
# save_recordings = false

# Recordings directory (only used if save_recordings = true)
# recordings_dir = "~/.voice-input/recordings"
```

### D. `install.sh` — корневой скрипт установки

По образу `gh-notify/install.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_SRC="$SCRIPT_DIR/systemd/voice-input.service"

# Check dependencies
for cmd in python3 xdotool whisper-cli; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found. Install it first."
    echo "  whisper-cli: cmake --install /projects/ai/whisper.cpp/build"
    echo "  xdotool: sudo apt install xdotool"
    exit 1
  fi
done

# Install Python package
if command -v pipx &>/dev/null; then
  pipx install "$SCRIPT_DIR" --force
  echo "✓ Installed via pipx"
else
  echo "pipx not found, installing via pip --user"
  pip install --user -e "$SCRIPT_DIR"
  echo "✓ Installed via pip"
fi

# Deploy systemd service
mkdir -p "$SYSTEMD_DIR"
cp "$SERVICE_SRC" "$SYSTEMD_DIR/"
echo "✓ Systemd service deployed"

# Enable and start
systemctl --user daemon-reload
systemctl --user enable --now voice-input
systemctl --user status voice-input --no-pager
echo "✓ Service enabled and started"
```

### E. `uninstall.sh` — корневой скрипт удаления

По образу `gh-notify/uninstall.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "==> Stopping and disabling voice-input service..."
systemctl --user disable --now voice-input || true

echo "==> Removing systemd unit files..."
rm -f "$SYSTEMD_DIR/voice-input.service"

echo "==> Reloading systemd daemon..."
systemctl --user daemon-reload

echo "==> Uninstalling Python package..."
if command -v pipx &>/dev/null; then
  pipx uninstall voice-input
  echo "    Uninstalled via pipx"
else
  pip uninstall -y voice-input --user
  echo "    Uninstalled via pip"
fi

echo "==> Done. Configuration and recordings in ~/.config/voice-input/ and ~/.voice-input/recordings/ were kept."
```

### F. `systemd/voice-input.service` — заменить ExecStart

```ini
[Unit]
Description=Voice Input Daemon — offline AI dictation
After=sound.target graphical-session.target
Requires=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/voice-input
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

### G. `scripts/install-service.sh` и `scripts/uninstall-service.sh` — удалить

Эти файлы больше не нужны, их функциональность в корневых `install.sh`/`uninstall.sh`.

### H. `README.md` — обновить секцию установки

```markdown
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
```

## Критерии готовности

- [ ] `pipx install .` + команда `voice-input` доступна
- [ ] `./install.sh` устанавливает всё с нуля (зависимости проверены заранее)
- [ ] systemd-сервис использует `%h/.local/bin/voice-input`
- [ ] `whisper-cli` ищется в `$PATH` (fallback на старые пути)
- [ ] `~/.config/voice-input/config.toml` создаётся при первом запуске
- [ ] `~/.voice-input/recordings/` создаётся при `save_recordings`
- [ ] `./uninstall.sh` чисто удаляет всё, оставляя конфиг
- [ ] `README.md` отражает новый процесс установки
- [ ] `python -c "import voice_daemon"` без ошибок
