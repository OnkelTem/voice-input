#!/usr/bin/env python3
import argparse
import datetime
import os
import queue
import subprocess
import tempfile
import threading
import time
import tomllib

import numpy as np
import pynput.keyboard as kb
import scipy.io.wavfile as wav
import sounddevice as sd

FS = 16000
RECORDING = False
SEGMENT_BUFFER = []
SILENCE_FRAMES = 0
SPEECH_ACTIVE = False
SEGMENT_QUEUE = queue.Queue()
TRANSCRIBER_THREAD = None
STREAM = None
PRESS_TIME = 0.0
RECORD_START = 0.0
ARM_TIMER = None
CFG = {}

FRAMES_PER_BLOCK = 512


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{ts}] [voice-input] {msg}", flush=True)


def load_config(config_path: str) -> dict:
    defaults = {
        "mode": "push-to-talk",
        "model": "/projects/ai/whisper.cpp/models/ggml-small.bin",
        "binary": "/projects/ai/whisper.cpp/build/bin/whisper-cli",
        "key": "insert",
        "prompt": "",
        "vad_threshold": 0.005,
        "vad_silence_ms": 2000,
        "vad_min_segment_ms": 300,
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
    cfg["_silence_limit_blocks"] = int(cfg["vad_silence_ms"] * FS / (FRAMES_PER_BLOCK * 1000))
    cfg["_min_segment_blocks"] = int(cfg["vad_min_segment_ms"] * FS / (FRAMES_PER_BLOCK * 1000))
    return cfg


def notify(msg: str) -> None:
    subprocess.run(["notify-send", "-t", "1500", "Voice Input", msg],
                   capture_output=True)


def callback(indata, frames, time, status):
    global SEGMENT_BUFFER, SILENCE_FRAMES, RECORDING, SPEECH_ACTIVE
    if not RECORDING:
        return
    SEGMENT_BUFFER.append(indata.copy())
    rms = np.sqrt(np.mean(indata**2))
    if rms > CFG["vad_threshold"]:
        SILENCE_FRAMES = 0
        SPEECH_ACTIVE = True
    else:
        SILENCE_FRAMES += 1
        if (SPEECH_ACTIVE
                and SILENCE_FRAMES > CFG["_silence_limit_blocks"]
                and len(SEGMENT_BUFFER) > CFG["_min_segment_blocks"]
                and SEGMENT_QUEUE.qsize() <= 5):
            data = np.concatenate(SEGMENT_BUFFER)
            SEGMENT_QUEUE.put(data)
            log(f"Segment queued ({len(data)/FS:.1f}s)")
            SEGMENT_BUFFER.clear()
            SILENCE_FRAMES = 0
            SPEECH_ACTIVE = False


def transcriber_loop():
    while True:
        segment = SEGMENT_QUEUE.get()
        if segment is None:
            break
        log(f"Transcribing segment ({len(segment)/FS:.1f}s)...")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
            wav.write(tmp, FS, segment)
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
                log(f"Segment transcribed: {text}")
            else:
                log("No speech detected in segment")
        except Exception as e:
            log(f"Transcription error: {e}")
        finally:
            os.unlink(tmp)


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
    ARM_TIMER = threading.Timer(0.3, _arm_timer)
    ARM_TIMER.start()


def _arm_timer():
    global RECORDING, STREAM, ARM_TIMER, RECORD_START, SILENCE_FRAMES, TRANSCRIBER_THREAD, SPEECH_ACTIVE
    ARM_TIMER = None
    RECORDING = True
    SEGMENT_BUFFER.clear()
    SILENCE_FRAMES = 0
    SPEECH_ACTIVE = False
    STREAM = sd.InputStream(samplerate=FS, channels=1, callback=callback, blocksize=FRAMES_PER_BLOCK)
    STREAM.start()
    RECORD_START = time.monotonic()
    notify("Recording...")
    log("Recording started")
    if TRANSCRIBER_THREAD is None or not TRANSCRIBER_THREAD.is_alive():
        TRANSCRIBER_THREAD = threading.Thread(target=transcriber_loop)
        TRANSCRIBER_THREAD.start()


def on_release(key):
    global RECORDING, SEGMENT_BUFFER, STREAM, ARM_TIMER, RECORD_START, PRESS_TIME, TRANSCRIBER_THREAD, SPEECH_ACTIVE
    if key != CFG["key"]:
        return
    if CFG["mode"] != "push-to-talk":
        return
    if ARM_TIMER is not None:
        ARM_TIMER.cancel()
        ARM_TIMER = None
        log("Key released — arm cancelled")
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
        notify("Cancelled")
        log("Recording cancelled (too short)")
        SEGMENT_BUFFER.clear()
        SILENCE_FRAMES = 0
        SPEECH_ACTIVE = False
        SEGMENT_QUEUE.put(None)
        if TRANSCRIBER_THREAD:
            TRANSCRIBER_THREAD.join()
        return
    if SEGMENT_BUFFER and SPEECH_ACTIVE:
        data = np.concatenate(SEGMENT_BUFFER)
        SEGMENT_QUEUE.put(data)
        log(f"Final segment queued ({len(data)/FS:.1f}s)")
        SEGMENT_BUFFER.clear()
    SEGMENT_QUEUE.put(None)
    if TRANSCRIBER_THREAD:
        TRANSCRIBER_THREAD.join()
    notify("Done")
    log("Transcription complete")


def main():
    global CFG
    CFG = build_config()
    if CFG["prompt"]:
        log(f"Config loaded, prompt={CFG['prompt'][:80]!r}")
    else:
        log("Config loaded, no prompt")
    log(f"Model: {CFG['model']}")
    log(f"Binary: {CFG['binary']}")
    log(f"Mode: {CFG['mode']}")
    log(f"Ready. Hold {CFG['key'].name} to record")
    notify("Voice input daemon started")
    with kb.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
