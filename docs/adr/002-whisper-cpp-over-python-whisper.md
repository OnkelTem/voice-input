# ADR 002: whisper.cpp over Python whisper implementations

Superseded by ADR 008 (in-process whisper.cpp via cffi)

## Status
Accepted

## Context
Multiple Whisper implementations exist: OpenAI's `openai-whisper` (Python), `faster-whisper` (Python/CTranslate2), and `whisper.cpp` (C++). We need fully offline, GPU-accelerated transcription on an NVIDIA RTX 3060 Ti 8GB.

## Decision
Use `whisper.cpp` compiled with CUDA support, invoked as a subprocess from the Python daemon.

## Consequences
- **Positive:** Significantly faster inference than Python implementations on the same GPU
- **Positive:** No Python-specific memory overhead for the model
- **Positive:** Can be used standalone (outside the daemon) for testing
- **Negative:** Subprocess call overhead (~100ms) for each transcription
- **Negative:** Language auto-detection is weaker than OpenAI's Python version; explicit `-l ru` required for Russian
