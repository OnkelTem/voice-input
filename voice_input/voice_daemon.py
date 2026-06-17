#!/usr/bin/env python3
import argparse
import datetime
import os
import subprocess
import sys
import signal
import scipy.io.wavfile as wav
import threading
import time
from enum import IntEnum
import ctypes
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QIcon
from importlib.resources import files as _pkg_files

import numpy as np
import pynput.keyboard as kb
import sounddevice as sd
from Xlib import display as xdisp

from voice_input.config import load_config
from voice_input.whisper_model import WhisperModel

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
LOCK = threading.Lock()

FRAMES_PER_BLOCK = 512


class AppState(IntEnum):
    IDLE = 0
    RECORDING = 1
    TRANSCRIBING = 2


TRAY_APP = None


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{ts}] [voice-input] {msg}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Voice input daemon")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    return parser.parse_args()


def build_config() -> dict:
    args = parse_args()
    config_path = args.config or os.path.expanduser("~/.config/voice-input/config.toml")
    cfg = load_config(config_path)
    cfg["key"] = getattr(kb.Key, cfg["key"].lower(), kb.Key.insert)
    return cfg


def _play_start_beep():
    beep_path = _pkg_files("voice_input") / "static" / "beep.wav"
    subprocess.run(["paplay", str(beep_path)], capture_output=True)


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
    with LOCK:
        if RECORDING or ARM_TIMER is not None:
            return
        log("Key pressed")
        PRESS_TIME = time.monotonic()
        ARM_TIMER = threading.Timer(0.05, _arm_timer)
        ARM_TIMER.start()


def _arm_timer():
    global RECORDING, STREAM, ARM_TIMER, RECORD_START, AUDIO_BUFFER
    with LOCK:
        if STREAM is not None or RECORDING:
            ARM_TIMER = None
            return
        ARM_TIMER = None
        AUDIO_BUFFER.clear()
        RECORDING = True
        STREAM = sd.InputStream(samplerate=FS, channels=1, callback=callback, blocksize=FRAMES_PER_BLOCK)
        STREAM.start()
        RECORD_START = time.monotonic()
    TRAY_APP.set_state(AppState.RECORDING)
    log("Arm timer fired \u2014 playing start beep")
    _play_start_beep()
    time.sleep(0.02)
    log("Recording started")

def on_release(key):
    global RECORDING, AUDIO_BUFFER, STREAM, ARM_TIMER, RECORD_START, PRESS_TIME
    if not _key_matches(key, CFG["key"]):
        return
    if CFG["mode"] != "push-to-talk":
        return
    with LOCK:
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
    with LOCK:
        if STREAM:
            STREAM.stop()
            STREAM.close()
            STREAM = None
    log("Stream stopped for transcription")
    with LOCK:
        elapsed = time.monotonic() - PRESS_TIME
    if elapsed < 2.0:
        log("Recording cancelled (too short)")
        with LOCK:
            AUDIO_BUFFER.clear()
        TRAY_APP.set_state(AppState.IDLE)
        return
    TRAY_APP.set_state(AppState.TRANSCRIBING)
    with LOCK:
        if AUDIO_BUFFER:
            data = np.concatenate(AUDIO_BUFFER)
            AUDIO_BUFFER.clear()
        else:
            data = np.array([], dtype=np.float32)
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
            key_released = False
            with LOCK:
                if RECORDING and STREAM is not None:
                    data = dpy.query_keymap()
                    bit_down = bool(data[keycode // 8] & (1 << (keycode % 8)))
                    if not bit_down:
                        log("Poll worker: key release detected")
                        RECORDING = False
                        key_released = True
            if key_released:
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

        self.icons = {
            AppState.IDLE: QIcon(str(_pkg_files("voice_input") / "static" / "idle.svg")),
            AppState.RECORDING: QIcon(str(_pkg_files("voice_input") / "static" / "recording.svg")),
            AppState.TRANSCRIBING: QIcon(str(_pkg_files("voice_input") / "static" / "transcribing.svg")),
        }

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


def main():
    global CFG, WHISPER_MODEL
    os.makedirs(os.path.expanduser("~/.config/voice-input"), exist_ok=True)
    config_path = os.path.expanduser("~/.config/voice-input/config.toml")
    if not os.path.exists(config_path):
        default_cfg = (_pkg_files("voice_input") / "templates" / "config.toml").read_text()
        with open(config_path, "w") as f:
            f.write(default_cfg)
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
