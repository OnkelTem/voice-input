# 008 — Save recordings for quality analysis

Сохранять все аудиозаписи в директорию для последующего анализа качества распознавания.

## Изменения

### 1. Конфиг (`~/.config/voice-input/config.toml`)

Добавить секцию:

```toml
save_recordings = true
recordings_dir = "~/.voice-input/recordings"
```
- `save_recordings` — включать/выключать сохранение (по умолчанию `false`)
- `recordings_dir` — путь к директории для сохранения (по умолчанию `~/.voice-input/recordings/`)

### 2. `voice_daemon.py`

1. В `load_config()` добавить дефолты:
   ```python
    "save_recordings": False,
   "recordings_dir": os.path.expanduser("~/.voice-input/recordings"),
   ```

2. В `on_release()` после успешной транскрипции (после строки 222 `log(f"Transcribed: {text}")`), но **до** `os.unlink(tmp)`:
   - Если `CFG["save_recordings"]` истинно:
     - Создать `CFG["recordings_dir"]` с `os.makedirs(exist_ok=True)`
     - Сформировать имя файла: `{timestamp}_{duration:.1f}s.wav`, где `timestamp` = `datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")`
     - Скопировать `tmp` в `<dir>/<filename>.wav` (через `shutil.copy2`)
     - Сохранить распознанный текст в `<dir>/<filename>.txt` (рядом с WAV)

3. Импорт `shutil` добавить в начало файла.

4. В `main()` добавить лог о состоянии save_recordings при старте.
5. В `on_release()` добавить логи сохранения WAV и TXT файлов.

### 3. Обновить `AGENTS.md`

Добавить запись о функции сохранения записей в секцию Architecture.

## Критерии готовности

- При `save_recordings = false` поведение не меняется (файл удаляется как сейчас)
- При `save_recordings = true` WAV + TXT появляются в `~/.voice-input/recordings/`
- Директория создаётся автоматически
- Имена не конфликтуют (секунды в timestamp достаточно)

### 4. Логирование

- При старте даемона: `Save recordings: enabled → ~/.voice-input/recordings/` или `Save recordings: disabled`
- При каждом сохранении: `Recording saved: <path>` и `Transcript saved: <path>`
