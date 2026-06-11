# 005 — Revert VAD + incremental transcription

## Goal

Remove the VAD (Voice Activity Detection) split-while-recording behaviour added
in task 003. Recording now accumulates a single buffer and transcribes as one
block on key release, as it did originally before 003.

## Changes

### `voice_daemon.py`

**Globals** — replace:
- `SEGMENT_BUFFER` → rename to `AUDIO_BUFFER = []`
- Remove: `SILENCE_FRAMES`, `SPEECH_ACTIVE`, `SEGMENT_QUEUE`, `TRANSCRIBER_THREAD`
- Keep: `RECORDING`, `STREAM`, `PRESS_TIME`, `RECORD_START`, `ARM_TIMER`, `APP_STATE`, `LISTENER`

**`callback()`** — reduce to simple accumulation:
```python
def callback(indata, frames, time, status):
    global AUDIO_BUFFER
    if not RECORDING:
        return
    AUDIO_BUFFER.append(indata.copy())
```

**`transcriber_loop()`** — delete entirely.

**`_arm_timer()`** — remove the `TRANSCRIBER_THREAD` startup block (last 3 lines).
Replace `SEGMENT_BUFFER.clear()` with `AUDIO_BUFFER.clear()`.

**`on_release()`** — rewrite to single-block transcription:
1. On short recording (<2s): clear buffer, `app_state.value = AppState.IDLE`, return
2. On valid release:
   - `app_state.value = AppState.TRANSCRIBING`
   - Concatenate all `AUDIO_BUFFER` into one NumPy array
   - Write a single temp WAV
   - Run `whisper-cli` once (same args as before: binary, model, prompt, lang auto)
   - `xdotool type` result
   - `app_state.value = AppState.IDLE`
   - Log result

**`load_config()`** — remove defaults: `vad_threshold`, `vad_silence_ms`, `vad_min_segment_ms`.

**`build_config()`** — remove lines computing `_silence_limit_blocks` and `_min_segment_blocks`.

### `README.md`

- Remove the VAD section (table with `vad_*` flags + paragraph about incremental transcription)
- Replace with: "During recording audio accumulates; transcription runs once on key release."
- Remove `vad_*` entries from the config TOML example (keep only `prompt`, `model`, `binary`, `key`, `mode`)

## Checklist

- [x] Rename globals, remove VAD/split globals
- [x] Simplify `callback()`
- [x] Delete `transcriber_loop()`
- [x] Clean `_arm_timer()`
- [x] Rewrite `on_release()` to single-block
- [x] Remove VAD config keys from `load_config()` / `build_config()`
- [x] Update README
- [x] Verify: `source .venv/bin/activate && python -c "import voice_daemon; print('OK')"`
- [x] Test: press, hold ~3s, release → text appears in active window
