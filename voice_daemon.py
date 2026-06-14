#!/usr/bin/env python3
import argparse
import datetime
import os
import subprocess
import sys
import signal
import tempfile
import scipy.io.wavfile as wav
import threading
import time
import tomllib
from enum import IntEnum
import ctypes
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PIL import Image, ImageDraw

import numpy as np
import pynput.keyboard as kb
import sounddevice as sd
from Xlib import display as xdisp

from whisper_model import WhisperModel

FS = 16000
RECORDING = False
AUDIO_BUFFER = []
STREAM = None
PRESS_TIME = 0.0
RECORD_START = 0.0
ARM_TIMER = None
CFG = {}
WHISPER_MODEL: WhisperModel | None = None
LISTENER = None
POLL_THREAD = None
STOP_POLL = False

FRAMES_PER_BLOCK = 512


class AppState(IntEnum):
    IDLE = 0
    RECORDING = 1
    TRANSCRIBING = 2


TRAY_APP = None


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{ts}] [voice-input] {msg}", flush=True)


def load_config(config_path: str) -> dict:
    defaults = {
        "mode": "push-to-talk",
        "model": "/projects/ai/whisper.cpp/models/ggml-small.bin",
        "key": "insert",
        "save_recordings": False,
        "recordings_dir": os.path.expanduser("~/.voice-input/recordings"),
        "whisper": {},
    }
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for k in defaults:
            if k in data:
                defaults[k] = data[k]
        if "whisper" in data:
            defaults["whisper"] = data["whisper"]
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        pass
    return defaults


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Voice input daemon")
    parser.add_argument("--model", type=str, default=None, help="Model path")
    parser.add_argument("--key", type=str, default=None, help="Toggle key name")
    parser.add_argument("--mode", type=str, default=None, help="Operating mode (push-to-talk or toggle)")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    return parser.parse_args()


def build_config() -> dict:
    args = parse_args()
    config_path = args.config or os.path.expanduser("~/.config/voice-input/config.toml")
    cfg = load_config(config_path)
    for k in ("model", "key", "mode"):
        v = getattr(args, k, None)
        if v is not None:
            cfg[k] = v
    cfg["key"] = getattr(kb.Key, cfg["key"].lower(), kb.Key.insert)
    return cfg


def _generate_tone(freq: float, duration_ms: int = 80, fs: int = 22050) -> np.ndarray:
    n = int(fs * duration_ms / 1000)
    t = np.arange(n) / fs
    tone = np.sin(2 * np.pi * freq * t)
    fade = int(fs * 0.005)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return (tone * 0.2).astype(np.float32)


def _play_tone(tone: np.ndarray, fs: int = 22050) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
        wav.write(tmp, fs, tone)
    try:
        subprocess.run(["paplay", tmp], capture_output=True)
    finally:
        os.unlink(tmp)


def play_start_beep():
    _play_tone(_generate_tone(1000, 120))


def generate_icons() -> dict[AppState, QIcon]:
    def _draw_mic(draw, color):
        draw.rounded_rectangle([(17, 8), (31, 28)], radius=4, fill=color)
        for y in (14, 18, 22):
            draw.line([(19, y), (29, y)], fill=(255, 255, 255, 128), width=1)
        draw.rectangle([(22, 28), (26, 36)], fill=color)
        draw.rectangle([(16, 35), (32, 37)], fill=color)

    icons = {}
    for state, color, overlay in (
        (AppState.IDLE, "#888888", None),
        (AppState.RECORDING, "#E53935", (38, 38, 5, "#E53935")),
        (AppState.TRANSCRIBING, "#1976D2", None),
    ):
        img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        _draw_mic(draw, color)
        if state == AppState.RECORDING:
            draw.ellipse([(33, 33), (43, 43)], fill="#E53935")
        elif state == AppState.TRANSCRIBING:
            for cx in (34, 37, 40):
                draw.ellipse([(cx - 2, 36), (cx + 2, 40)], fill="#1976D2")
        qimage = QImage(img.tobytes(), 48, 48, QImage.Format_RGBA8888)
        pix = QPixmap.fromImage(qimage)
        icons[state] = QIcon(pix)
    return icons


def callback(indata, frames, time, status):
    global AUDIO_BUFFER
    if not RECORDING:
        return
    AUDIO_BUFFER.append(indata.copy())


def _key_matches(event_key, target):
    if event_key == target:
        return True
    try:
        return event_key.vk == target.value.vk
    except (AttributeError, TypeError):
        return False


def on_press(key):
    global RECORDING, ARM_TIMER, PRESS_TIME
    if not _key_matches(key, CFG["key"]):
        return
    if CFG["mode"] != "push-to-talk":
        return
    if RECORDING or ARM_TIMER is not None:
        return
    log("Key pressed")
    PRESS_TIME = time.monotonic()
    ARM_TIMER = threading.Timer(0.05, _arm_timer)
    ARM_TIMER.start()


def _arm_timer():
    global RECORDING, STREAM, ARM_TIMER, RECORD_START, AUDIO_BUFFER
    ARM_TIMER = None
    TRAY_APP.set_state(AppState.RECORDING)
    AUDIO_BUFFER.clear()
    log("Arm timer fired \u2014 playing start beep")
    play_start_beep()
    time.sleep(0.02)
    RECORDING = True
    STREAM = sd.InputStream(samplerate=FS, channels=1, callback=callback, blocksize=FRAMES_PER_BLOCK, dtype=np.int16)
    STREAM.start()
    RECORD_START = time.monotonic()
    log("Recording started")

def on_release(key):
    global RECORDING, AUDIO_BUFFER, STREAM, ARM_TIMER, RECORD_START, PRESS_TIME
    if not _key_matches(key, CFG["key"]):
        return
    if CFG["mode"] != "push-to-talk":
        return
    if ARM_TIMER is not None:
        ARM_TIMER.cancel()
        ARM_TIMER = None
        log("Key released \u2014 arm cancelled")
        return
    if not RECORDING:
        return
    RECORDING = False
    if STREAM:
        STREAM.stop()
        STREAM.close()
        STREAM = None
    log("Key released")
    _stop_stream_and_transcribe()


def _stop_stream_and_transcribe():
    global AUDIO_BUFFER, STREAM, RECORD_START, PRESS_TIME
    if STREAM:
        STREAM.stop()
        STREAM.close()
        STREAM = None
    log("Stream stopped for transcription")
    elapsed = time.monotonic() - PRESS_TIME
    if elapsed < 2.0:
        log("Recording cancelled (too short)")
        AUDIO_BUFFER.clear()
        TRAY_APP.set_state(AppState.IDLE)
        return
    TRAY_APP.set_state(AppState.TRANSCRIBING)
    if AUDIO_BUFFER:
        data = np.concatenate(AUDIO_BUFFER)
        AUDIO_BUFFER.clear()
        log(f"Transcribing ({len(data)/FS:.1f}s)...")
        stem = None
        if CFG.get("save_recordings", False):
            rec_dir = CFG["recordings_dir"]
            os.makedirs(rec_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            duration = len(data) / FS
            stem = f"{ts}_{duration:.1f}s"
            wav_path = os.path.join(rec_dir, stem + ".wav")
            wav.write(wav_path, FS, data)
            log(f"Recording saved: {wav_path}")
        text = ""
        if WHISPER_MODEL is not None:
            try:
                text = WHISPER_MODEL.transcribe(data)
            except Exception as e:
                log(f"Transcription error: {e}")
        if text:
            if text[-1] in ".?!":
                text += " "
            subprocess.run(["xdotool", "type", text])
            log(f"Transcribed: {text}")
            if CFG.get("save_recordings", False) and stem:
                txt_path = os.path.join(rec_dir, stem + ".txt")
                with open(txt_path, "w") as tf:
                    tf.write(text + "\n")
                log(f"Transcript saved: {txt_path}")
        else:
            log("No speech detected")
    TRAY_APP.set_state(AppState.IDLE)
    log("Transcription complete")


def _x11_poll_worker():
    global RECORDING
    try:
        dpy = xdisp.Display()
        target_vk = CFG["key"].value.vk
        keycode = dpy.keysym_to_keycode(target_vk)
        if keycode == 0:
            log("Poll worker: could not resolve X11 keycode, disabling")
            dpy.close()
            return
        log(f"Poll worker started, tracking keycode={keycode} (vk={hex(target_vk)})")
        while not STOP_POLL:
            if RECORDING:
                data = dpy.query_keymap()
                bit_down = bool(data[keycode // 8] & (1 << (keycode % 8)))
                if not bit_down:
                    log("Poll worker: key release detected")
                    RECORDING = False
                    _stop_stream_and_transcribe()
            time.sleep(0.05)
        dpy.close()
        log("Poll worker stopped")
    except Exception as e:
        log(f"Poll worker error: {e}")


class TrayApp(QObject):
    state_changed = pyqtSignal(int)

    def __init__(self, cfg):
        super().__init__()
        global TRAY_APP
        TRAY_APP = self
        self.cfg = cfg
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.icons = generate_icons()

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.icons[AppState.IDLE])
        self.tray.setToolTip("Voice Input \u2014 Idle")
        self.tray.setVisible(True)

        menu = QMenu()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)

        self.state_changed.connect(self._on_state_changed)

    def set_state(self, state: AppState):
        self.state_changed.emit(state.value)

    def _on_state_changed(self, state_val: int):
        state = AppState(state_val)
        self.tray.setIcon(self.icons[state])
        tips = {
            AppState.IDLE: "Voice Input \u2014 Idle",
            AppState.RECORDING: "Voice Input \u2014 Recording...",
            AppState.TRANSCRIBING: "Voice Input \u2014 Transcribing...",
        }
        self.tray.setToolTip(tips[state])

    def quit(self):
        global RECORDING, STREAM, LISTENER, STOP_POLL, POLL_THREAD
        STOP_POLL = True
        if LISTENER:
            LISTENER.stop()
        if RECORDING:
            RECORDING = False
            if STREAM:
                STREAM.stop()
                STREAM.close()
                STREAM = None
        self.app.quit()

    def run(self):
        global LISTENER, STOP_POLL, POLL_THREAD
        LISTENER = kb.Listener(on_press=on_press, on_release=on_release)
        LISTENER.daemon = True
        LISTENER.start()
        STOP_POLL = False
        POLL_THREAD = threading.Thread(target=_x11_poll_worker, daemon=True)
        POLL_THREAD.start()
        return self.app.exec()


DEFAULT_CONFIG_TOML = """# Voice Input configuration
# Uncomment and modify values as needed.

# Path to whisper model file (.bin)
# model = "/projects/ai/whisper.cpp/models/ggml-small.bin"

# Hotkey key name: shift_r, insert, f1, f2, space, etc.
# key = "insert"

# Operating mode: "push-to-talk" or "toggle"
# mode = "push-to-talk"

# Save recordings for quality analysis (saves WAV + transcript to recordings_dir)
# save_recordings = false

# Directory for saved recordings (only used if save_recordings = true)
# recordings_dir = "~/.voice-input/recordings"

[whisper]
# Number of threads to use during computation
# n_threads = 4

# Maximum number of text context tokens to accumulate across calls (0 = disable context)
# n_max_text_ctx = 224

# Spoken language: "auto" for auto-detect, or language code like "en", "ru", "de"
# language = "auto"

# Sampling temperature (0.0 = greedy, up to 1.0)
# temperature = 0.0

# Temperature increment for fallback on greedy failure (0 = no fallback)
# temperature_inc = 0.2

# Suppress non-speech tokens
# suppress_nst = false

# Do not use past transcription as context for the decoder
# no_context = false

# Translate from source language to English
# translate = false

# Force single segment output
# single_segment = false

# Maximum segment length in characters (0 = no limit)
# max_len = 0

# Split on word boundaries rather than on token boundaries
# split_on_word = false

# Suppress blank output at the beginning of transcription
# suppress_blank = true

# Do not generate timestamps
# no_timestamps = true

# Initial prompt for transcription context (max n_text_ctx / 2 tokens)
# initial_prompt = ""

# Always prepend initial_prompt to the start of every decode window
# carry_initial_prompt = false

# Regular expression matching tokens to suppress
# suppress_regex = ""

# Enable built-in Voice Activity Detection in whisper.cpp
# vad = false

# Print special tokens (e.g., [SOT], [EOT], [BLANK])
# print_special = false

# Enable debug mode
# debug_mode = false
"""

def main():
    global CFG, WHISPER_MODEL
    os.makedirs(os.path.expanduser("~/.config/voice-input"), exist_ok=True)
    config_path = os.path.expanduser("~/.config/voice-input/config.toml")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write(DEFAULT_CONFIG_TOML)
    CFG = build_config()
    try:
        WHISPER_MODEL = WhisperModel(
            CFG["model"],
            log_fn=log,
            overrides=CFG.get("whisper", {}),
        )
        log(f"Whisper model loaded: {CFG['model']}")
    except Exception as e:
        log(f"Failed to load whisper model: {e}")
        sys.exit(1)
    if CFG.get("save_recordings", False):
        os.makedirs(CFG["recordings_dir"], exist_ok=True)
        log(f"Save recordings: enabled \u2192 {CFG['recordings_dir']}")
    else:
        log("Save recordings: disabled")
    log(f"Mode: {CFG['mode']}")
    log(f"Ready. Hold {CFG['key'].name} to record")
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        exit_code = TrayApp(CFG).run()
    finally:
        if WHISPER_MODEL is not None:
            WHISPER_MODEL.free()
            WHISPER_MODEL = None
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
