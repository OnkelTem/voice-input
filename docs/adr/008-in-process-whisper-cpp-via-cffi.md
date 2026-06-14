# 008 — In-process whisper.cpp через cffi

## Статус
Accepted

## Контекст
Изначально (ADR 002) whisper.cpp вызывался как subprocess (`whisper-cli`). Это давало изоляцию, но имело недостатки:

- ~100ms overhead на каждый вызов
- Невозможность накопления текстового контекста между транскрипциями (`--max-context` бесполезен, т.к. каждый вызов — новый процесс)
- Аудио записывалось во временный WAV-файл, затем читалось whisper-cli
- Дополнительная зависимость: собранный бинарник `whisper-cli` в $PATH

## Решение
Заменить subprocess на in-process вызовы `libwhisper.so.1` через Python cffi:

- `whisper_helper.so` грузится через `ffi.dlopen()`, который линкуется к `libwhisper.so.1`
- Структуры (`whisper_full_params`, `whisper_context_params`) объявляются в `ffi.cdef()` прямым копированием из `whisper.h`
- Модель загружается один раз при старте демона через `whisper_init_from_file_with_params()`, контекст живёт всё время работы
- Транскрипция: `whisper_full()` принимает numpy-массив напрямую, без записи на диск
- Текстовый контекст накапливается между вызовами через `n_max_text_ctx = 224` (половина от `n_text_ctx` модели)
- Параметры whisper.cpp конфигурируются через секцию `[whisper]` в `config.toml` и применяются через `_apply_overrides()`

### Почему cffi, а не ctypes
Структура `whisper_full_params` (~250 байт) передаётся по значению. cffi не может корректно передать `whisper_full_params` по значению (struct-by-value ABI mismatch). C-обёртка `whisper_helper.c` принимает `params*` по указателю и разыменовывает на стороне C, вызывая `whisper_full(ctx, *params, ...)`. Параметры создаются через `whisper_full_default_params_by_ref()` (heap, C layout)

## Последствия
- **+** Контекст между фразами: whisper помнит до 224 токенов предыдущего текста
- **+** Нет subprocess overhead
- **+** Нет WAV tempfile для транскрипции
- **+** Нет зависимости от собранного `whisper-cli`
- **+** Все опции whisper.cpp доступны через `config.toml`
- **−** Модель живёт в памяти процесса (1533 MB для medium)
- **−** Сбой whisper роняет демона (но это крайне редко)
- **−** Зависимость от cffi (устанавливается в .venv)

## Конфигурация
```toml
[whisper]
n_threads = 4
n_max_text_ctx = 224
language = "auto"
temperature = 0.0
temperature_inc = 0.2
suppress_nst = false
```
