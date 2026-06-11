# 009 — Adjust recording start timing

Сократить arm-таймер и перенести начало записи на после окончания beep'а.

## Мотивация

Текущий порядок: нажатие → 300ms arm → beep (120ms) + запись одновременно.
Проблема: beep попадает в аудиобуфер, первые ~100ms записи — это звук beep'а.

Новый порядок: нажатие → 50ms arm → beep (120ms) → 20ms пауза → запись.
Beep в запись не попадает.

## Изменения

### `voice_daemon.py`

1. В `on_press()` (строка 164): `threading.Timer(0.3, _arm_timer)` → `threading.Timer(0.05, _arm_timer)`.

2. В `_arm_timer()` изменить порядок:
   - Убрать `RECORDING = True` и `STREAM.start()` до beep'а
   - Сначала: `app_state.value = AppState.RECORDING`, очистить буфер, залогировать arm
   - Потом: синхронный `play_start_beep()` (блокируется, пока звук не доиграет)
   - Потом: `time.sleep(0.02)` (20ms пауза)
   - Потом: `RECORDING = True`, открыть `sd.InputStream`, `STREAM.start()`, `RECORD_START = time.monotonic()`, залогировать "Recording started"

## Критерии готовности

- `import time` уже есть в начале файла
- Arm-таймер 50ms вместо 300ms
- Аудиобуфер пуст, когда начинается beep
- beep полностью отыгран + 20ms до начала записи
- `python -c "import voice_daemon"` — без ошибок
