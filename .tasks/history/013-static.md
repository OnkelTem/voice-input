# 013 — Вынос статики в файлы, пакетная структура

## Goal

Убрать из кода runtime-генерацию иконок (Pillow), звука (NumPy) и дефолтного конфига (строка в Python). Вынести их в файлы, которые генерируются сервисными скриптами и пакуются в wheel. Перевести проект на пакетную структуру для корректной установки через pipx.

## Changes

### A. Пакет `voice_input/`

Исходники перемещены из корня в `voice_input/`:
- `voice_daemon.py`
- `whisper_model.py`
- `whisper_helper.so` (теперь включается в `package_data`)

### B. Статика `voice_input/static/`

Вместо генерации иконок через Pillow и звука через NumPy + temp WAV:
- `idle.svg`, `recording.svg`, `transcribing.svg` — готовые SVG
- `beep.wav` — 1000 Гц, 120 мс, 16-bit mono

Загружаются через `importlib.resources.files("voice_input")`.

### C. Шаблоны `voice_input/templates/`

`config.toml` — вместо константы `DEFAULT_CONFIG_TOML` в Python. При первом запуске копируется в `~/.config/voice-input/config.toml`.

### D. Сервисные скрипты `scripts/`

- `generate_icons.py` — генерирует 3 SVG (только stdlib)
- `generate_sounds.py` — генерирует beep.wav (только stdlib)

Не входят в пакет, запускаются через `make static`.

### E. `Makefile`

Добавлена цель `static`, `all` теперь зависит от `static` + `whisper_helper.so`.

### F. `pyproject.toml`

- Entry point: `voice-input = "voice_input.voice_daemon:main"`
- `package_data` включает `static/*`, `templates/*`, `whisper_helper.so`
- Pillow удалён из зависимостей

### G. `install.sh`

Добавлен `make static` перед установкой пакета.

## Criteria

- [ ] `make static` генерирует SVG и WAV в `voice_input/static/`
- [ ] `make` собирает статику + whisper_helper.so
- [ ] `python -m voice_input.voice_daemon` запускается без ошибок
- [ ] `pipx install .` устанавливает пакет со статикой
- [ ] `voice-input` команда доступна после установки
- [ ] Иконки в трее отображаются корректно
- [ ] Бип воспроизводится при старте записи
- [ ] Дефолтный конфиг создаётся при первом запуске
- [ ] Старые файлы удалены: `voice_daemon.py`, `whisper_model.py`, `whisper_helper.so`, `icons/`, `favicon.svg`
