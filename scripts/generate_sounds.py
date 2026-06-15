#!/usr/bin/env python3
import math
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "voice_input" / "static"
OUT.mkdir(parents=True, exist_ok=True)

FS = 22050
DURATION_MS = 120
FREQ = 1000.0
AMPLITUDE = 0.2
FADE_MS = 5

n_samples = int(FS * DURATION_MS / 1000)
fade_samples = int(FS * FADE_MS / 1000)

samples = []
for i in range(n_samples):
    t = i / FS
    val = math.sin(2 * math.pi * FREQ * t) * AMPLITUDE
    if i < fade_samples:
        val *= i / fade_samples
    if i >= n_samples - fade_samples:
        val *= (n_samples - 1 - i) / fade_samples
    samples.append(int(val * 32767))

with wave.open(str(OUT / "beep.wav"), "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(FS)
    wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
