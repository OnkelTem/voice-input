#!/usr/bin/env python3
import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from enum import IntEnum
import ctypes
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PIL import Image, ImageDraw

import numpy as np
import pynput.keyboard as kb
import scipy.io.wavfile as wav
import sounddevice as sd

FS = 16000
RECORDING = False
AUDIO_BUFFER = []
STREAM = None
PRESS_TIME = 0.0
RECORD_START = 0.0
ARM_TIMER = None
CFG = {}
LISTENER = None

FRAMES_PER_BLOCK = 512


class AppState(IntEnum):
    IDLE = 0
    RECORDING = 1
    TRANSCRIBING = 2


app_state = ctypes.c_int(0)


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{ts}] [voice-input] {msg}", flush=True)


def load_config(config_path: str) -> dict:
    binary_default = shutil.which("whisper-cli") or "/projects/ai/whisper.cpp/build/bin/whisper-cli"
    model_derived = os.path.join(os.path.dirname(binary_default), "../models/ggml-small.bin")
    model_default = model_derived if os.path.exists(model_derived) else "/projects/ai/whisper.cpp/models/ggml-small.bin"
    defaults = {
        "mode": "push-to-talk",
        "model": model_default,
        "binary": binary_default,
        "key": "insert",
        "prompt": "",
        "save_recordings": False,
        "recordings_dir": os.path.expanduser("~/.voice-input/recordings"),
    }
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for k in defaults:
            if k in data:
                defaults[k] = data[k]
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        pass
    return defaults


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Voice input daemon")
    parser.add_argument("--prompt", type=str, default=None, help="Initial prompt text")
    parser.add_argument("--model", type=str, default=None, help="Model path")
    parser.add_argument("--binary", type=str, default=None, help="Whisper binary path")
    parser.add_argument("--key", type=str, default=None, help="Toggle key name")
    parser.add_argument("--mode", type=str, default=None, help="Operating mode (push-to-talk or toggle)")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    return parser.parse_args()


def build_config() -> dict:
    args = parse_args()
    config_path = args.config or os.path.expanduser("~/.config/voice-input/config.toml")
    cfg = load_config(config_path)
    for k in ("prompt", "model", "binary", "key", "mode"):
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


def on_press(key):
    global RECORDING, ARM_TIMER, PRESS_TIME
    if key != CFG["key"]:
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
    app_state.value = AppState.RECORDING
    AUDIO_BUFFER.clear()
    log("Arm timer fired — playing start beep")
    play_start_beep()
    time.sleep(0.02)
    RECORDING = True
    STREAM = sd.InputStream(samplerate=FS, channels=1, callback=callback, blocksize=FRAMES_PER_BLOCK)
    STREAM.start()
    RECORD_START = time.monotonic()
    log("Recording started")

def on_release(key):
    global RECORDING, AUDIO_BUFFER, STREAM, ARM_TIMER, RECORD_START, PRESS_TIME
    if key != CFG["key"]:
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
    elapsed = time.monotonic() - PRESS_TIME
    if elapsed < 2.0:
        log("Recording cancelled (too short)")
        AUDIO_BUFFER.clear()
        app_state.value = AppState.IDLE
        return
    app_state.value = AppState.TRANSCRIBING
    if AUDIO_BUFFER:
        data = np.concatenate(AUDIO_BUFFER)
        AUDIO_BUFFER.clear()
        log(f"Transcribing ({len(data)/FS:.1f}s)...")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
            wav.write(tmp, FS, data)
        try:
            args = [CFG["binary"], "-m", CFG["model"], "-f", tmp, "--no-timestamps"]
            if CFG["prompt"]:
                args += ["--prompt", CFG["prompt"]]
            args += ["-l", "auto"]
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            text = result.stdout.strip()
            if text:
                if text[-1] in ".?!":
                    text += " "
                subprocess.run(["xdotool", "type", text])
                log(f"Transcribed: {text}")
                if CFG.get("save_recordings", False):
                    rec_dir = CFG["recordings_dir"]
                    os.makedirs(rec_dir, exist_ok=True)
                    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    duration = len(data) / FS
                    stem = f"{ts}_{duration:.1f}s"
                    wav_path = os.path.join(rec_dir, stem + ".wav")
                    txt_path = os.path.join(rec_dir, stem + ".txt")
                    shutil.copy2(tmp, wav_path)
                    log(f"Recording saved: {wav_path}")
                    with open(txt_path, "w") as tf:
                        tf.write(text + "\n")
                    log(f"Transcript saved: {txt_path}")
            else:
                log("No speech detected")
        except Exception as e:
            log(f"Transcription error: {e}")
        finally:
            os.unlink(tmp)
    app_state.value = AppState.IDLE
    log("Transcription complete")


class TrayApp:
    def __init__(self, cfg):
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

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_icon)
        self.timer.start(200)
        self._prev_state = AppState.IDLE

    def update_icon(self):
        state = AppState(app_state.value)
        if state != self._prev_state:
            self.tray.setIcon(self.icons[state])
            self._prev_state = state
        tips = {
            AppState.IDLE: "Voice Input \u2014 Idle",
            AppState.RECORDING: "Voice Input \u2014 Recording...",
            AppState.TRANSCRIBING: "Voice Input \u2014 Transcribing...",
        }
        self.tray.setToolTip(tips[state])

    def quit(self):
        global RECORDING, STREAM, LISTENER
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
        global LISTENER
        LISTENER = kb.Listener(on_press=on_press, on_release=on_release)
        LISTENER.daemon = True
        LISTENER.start()
        self.timer.start()
        sys.exit(self.app.exec())


DEFAULT_CONFIG_TOML = """# Voice Input configuration
# Uncomment and modify values as needed.

# Transcription context prompt
# prompt = ""

# Path to whisper-cli binary
# binary = ""

# Path to whisper model file
# model = ""

# Hotkey: shift_r, insert, f1, f2, space, etc.
# key = "insert"

# Operating mode: "push-to-talk" or "toggle"
# mode = "push-to-talk"

# Save recordings for quality analysis
# save_recordings = false

# Recordings directory (only used if save_recordings = true)
# recordings_dir = "~/.voice-input/recordings"
"""

def main():
    global CFG
    os.makedirs(os.path.expanduser("~/.config/voice-input"), exist_ok=True)
    config_path = os.path.expanduser("~/.config/voice-input/config.toml")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write(DEFAULT_CONFIG_TOML)
    CFG = build_config()
    if CFG["prompt"]:
        log(f"Config loaded, prompt={CFG['prompt'][:80]!r}")
    else:
        log("Config loaded, no prompt")
    log(f"Model: {CFG['model']}")
    log(f"Binary: {CFG['binary']}")
    if CFG.get("save_recordings", False):
        os.makedirs(CFG["recordings_dir"], exist_ok=True)
        log(f"Save recordings: enabled → {CFG['recordings_dir']}")
    else:
        log("Save recordings: disabled")
    log(f"Mode: {CFG['mode']}")
    log(f"Ready. Hold {CFG['key'].name} to record")
    TrayApp(CFG).run()


if __name__ == "__main__":
    main()
