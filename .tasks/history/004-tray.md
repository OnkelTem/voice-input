# 004 — System tray icon with state indication

## Goal

Currently the daemon only uses `notify-send` for transient notifications. It's
unclear whether:
- the program is running at all;
- recording is in progress;
- transcription is being processed.

Add a system tray icon that shows the current state at a glance.

## Architecture

### Components

- **PyQt5** (`QSystemTrayIcon`) — native tray icon
- **Pillow** — generates three 48×48 RGBA PNGs in memory
- **`ctypes.c_int`** — thread-safe shared state between pynput callbacks and Qt timer

### States (`AppState`)

```
IDLE = 0         — waiting for key press
RECORDING = 1    — audio capture active
TRANSCRIBING = 2 — whisper-cli processing final segment(s)
```

### Transitions

```
IDLE → RECORDING      : _arm_timer() fires (key held ≥300ms)
RECORDING → IDLE      : on_release() — recording < 2s (cancel)
RECORDING → TRANSCRIBING : on_release() — valid recording, transcription starts
TRANSCRIBING → IDLE   : transcriber_loop finished (join returned)
```

### Icons (Pillow, 48×48, RGBA)

All three share the same microphone shape (rounded rectangle body + horizontal
grille lines + stand). They differ in color and a small overlay element:

- **IDLE**: gray `#888888` microphone, no overlay
- **RECORDING**: red `#E53935` microphone + red circle ⏺ bottom-right
- **TRANSCRIBING**: blue `#1976D2` microphone + three dots `⋯` bottom-right

Icons are generated once at startup, stored in `dict[AppState, QIcon]`.

### Threads

```
┌─ Main (Qt event loop) ────────────────────────┐
│  QApplication                                 │
│  QSystemTrayIcon.setIcon(state)     │
│  QTimer(200ms) → poll c_int → setIcon         │
│  Context menu: Quit                           │
└───────────────────────────────────────────────┘

┌─ Daemon thread: pynput Listener ──────────────┐
│  on_press / on_release → modify c_int          │
└───────────────────────────────────────────────┘

┌─ Daemon thread: transcriber_loop ─────────────┐
│  (unchanged from current code)                │
└───────────────────────────────────────────────┘
```

The main thread no longer blocks on `kb.Listener.join()`. Instead:
- listener starts as a `daemon=True` thread
- `QApplication.exec()` keeps the process alive

### Context menu

Single **Quit** action:
1. Stop pynput listener
2. Stop audio stream (if recording)
3. Push `None` sentinel into segment queue
4. Join transcriber thread
5. Call `app.quit()`

### Callback changes

**`_arm_timer()`** — after `RECORDING = True`:
```python
app_state.value = AppState.RECORDING
```

**`on_release()`** — before queuing `None` sentinel:
```python
app_state.value = AppState.TRANSCRIBING
```
After `TRANSCRIBER_THREAD.join()`:
```python
app_state.value = AppState.IDLE
```
On cancel (short recording):
```python
app_state.value = AppState.IDLE
```

## Files to change

### `voice_daemon.py`

- Imports: `enum`, `ctypes`, `PyQt5` modules, `PIL.Image/ImageDraw`
- `class AppState(IntEnum)` — enum for the three states
- `app_state: ctypes.c_int` — global shared state variable
- `def generate_icons() -> dict[AppState, QIcon]` — draw three icons with Pillow
- `class TrayApp`:
  - `__init__`: `QApplication`, `QSystemTrayIcon`, `QTimer(200ms)`, `QMenu`
  - `update_icon()`: read `app_state.value`, `setIcon()`, set tooltip
  - `quit()`: cleanup, `app.quit()`
  - `run()`: start pynput listener daemon, `app.exec()`
- In `main()`: replace `kb.Listener(...).join()` with `TrayApp(CFG).run()`
- Update callbacks: `_arm_timer`, `on_release`

### `pyproject.toml`

Add to `dependencies`:
```toml
"PyQt5>=5.15",
"Pillow>=10.2",
```

### `README.md` (optional)

Mention system tray indicator in the description.

## Checklist

- [ ] Add `AppState` enum and `app_state` shared variable
- [ ] Write `generate_icons()` with three distinct icons
- [ ] Write `TrayApp` class
- [ ] Integrate `TrayApp` into `main()`
- [ ] Update `_arm_timer()` — set `state = RECORDING`
- [ ] Update `on_release()` — set `state = TRANSCRIBING / IDLE`
- [ ] Context menu: Quit with proper cleanup
- [ ] Add `PyQt5` and `Pillow` to `pyproject.toml`
- [ ] Test: startup, record, transcribe, quit via menu
