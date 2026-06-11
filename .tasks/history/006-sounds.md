# 006 — Start recording beep

## Goal

Add a short notification sound when recording starts, so the user gets
audible feedback without needing to look at the tray icon.

## Design

### Tone generation

All sounds are generated programmatically with existing dependencies
(`numpy` + `scipy.io.wavfile`). No external audio assets required.

```python
def _generate_tone(freq: float, duration_ms: int = 120, fs: int = 22050) -> np.ndarray:
    """Sine wave + 5ms fade in/out to prevent clicks."""
    n = int(fs * duration_ms / 1000)
    t = np.arange(n) / fs
    tone = np.sin(2 * np.pi * freq * t)
    fade = int(fs * 0.005)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return (tone * 0.5).astype(np.float32)
```

### Playback

Write tone to a temp WAV, play via `paplay` (PulseAudio), then delete.

```python
def _play_tone(tone: np.ndarray, fs: int = 22050) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
        wav.write(tmp, fs, tone)
    try:
        subprocess.run(["paplay", tmp], capture_output=True)
    finally:
        os.unlink(tmp)
```

### Start beep only

| Sound | Frequency | Duration | Called from |
|---|---|---|---|
| `play_start_beep()` | 1000 Hz (short high peep) | 120ms | `_arm_timer()` — before `InputStream.start()` |

### Placement in code

**`_arm_timer()`** — add after `log("Recording started")`, before `InputStream.start()`:
```python
    log("Recording started")
    play_start_beep()
    STREAM = sd.InputStream(...)
    STREAM.start()
```


## Files to change

### `voice_daemon.py`

- Add three new functions: `_generate_tone()`, `_play_tone()`, and `play_start_beep()`
- In `_arm_timer()`: call `play_start_beep()` before starting the stream

## Tuning knobs (can be adjusted later)

| Parameter | Current value |
|---|---|
| Start frequency | 1000 Hz |
| Duration | 120 ms |
| Volume | 0.5 amplitude |
| Fade | 5 ms in/out |

## Checklist

- [ ] Add `_generate_tone()`, `_play_tone()`, `play_start_beep()`
- [ ] Call `play_start_beep()` in `_arm_timer()`
- [ ] Verify: `source .venv/bin/activate && python -c "import voice_daemon; print('OK')"`
