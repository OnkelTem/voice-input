# 007 — Replace INSERT key with Right Shift for push-to-talk

## Goal

Change the default push-to-talk key from `Insert` to `Right Shift`
(`shift_r` in pynput) because INSERT interferes with VS Code (cursor blinking).

## Design

### Key selection

- **Chosen key**: Right Shift (`kb.Key.shift_r` in pynput)
- **Reason**: Rarely used alone in editors/IDEs, no known conflicts with VS Code
- **Trade-off**: If other keys are pressed while Right Shift is held, they produce
  uppercase/shifted characters. Since transcription fires only after the key is
  released, this is not an issue in practice.

### Config change

The daemon resolves the key at startup via:
```python
cfg["key"] = getattr(kb.Key, cfg["key"].lower(), kb.Key.insert)
```

Setting `cfg["key"]` to `"shift_r"` resolves to `kb.Key.shift_r`.

### Changes

| File | Line | Change |
|---|---|---|
| `voice_daemon.py` | 55 | `"key": "insert"` → `"key": "shift_r"` |
| `~/.config/voice-input/config.toml` | — | Add `key = "shift_r"` |

## Files to change

### `voice_daemon.py` (line 55)

```python
"key": "shift_r",
```

### `~/.config/voice-input/config.toml`

```toml
key = "shift_r"
```

## Checklist

- [ ] Change default in `voice_daemon.py:55` from `"insert"` to `"shift_r"`
- [ ] Add `key = "shift_r"` to `~/.config/voice-input/config.toml`
- [ ] Verify: start daemon, hold Right Shift → recording starts, release → transcribes
