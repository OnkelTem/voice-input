# 012 — Persistent whisper.cpp контекст через Python bindings

## Goal

Заменить архитектуру stateless subprocess (`whisper-cli`) на постоянное in-process подключение к whisper.cpp через Pybind11-биндинги `whispercpp`. Модель загружается один раз при старте демона, и контекст между транскрипциями накапливается через `n_max_text_ctx`.

## Changes

### A. `pip install whispercpp` в .venv

### B. `whisper_model.py` — новый файл с классом `WhisperModel`

Загружает модель через `Whisper.from_pretrained()`, настраивает `language="auto"`, `no_timestamps=True`, `n_max_text_ctx=224`. Метод `transcribe(samples: np.ndarray) -> str` передаёт аудио напрямую в whisper.cpp без записи на диск.

### C. `voice_daemon.py` — замена subprocess на WhisperModel

- Убраны `tempfile`, subprocess `whisper-cli` вызов, WAV-запись в temp (кроме save_recordings)
- `_stop_stream_and_transcribe()` вызывает `WHISPER_MODEL.transcribe(data)`
- Инициализация `WhisperModel` при старте, `free()` при выходе
- Убраны CLI-флаги `--binary` и `--prompt`, убраны ключи `binary`/`prompt` из конфига
- `save_recordings` сохранён: wav пишется до `transcribe`, txt — после

### D. `pyproject.toml` — добавлена зависимость `whispercpp`

### E. `AGENTS.md`, `README.md` — обновлены (whisper-cli → whispercpp)

### F. `install.sh` — убрана проверка `whisper-cli`

## Criteria

- [ ] `.venv/bin/pip install whispercpp` выполняется без ошибок
- [ ] Модель загружается один раз при старте демона
- [ ] Транскрипция работает через `WhisperModel.transcribe(data)`, без subprocess/wav-tempfile
- [ ] Контекст накапливается между вызовами (фраза 2 видит фразу 1)
- [ ] `save_recordings` продолжает работать
- [ ] `xdotool type` выводит текст как раньше
- [ ] Graceful cleanup при выходе (вызов `free()`)
- [ ] `python -c "import voice_daemon"` без ошибок
