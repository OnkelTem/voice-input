import argparse
import os

import scipy.io.wavfile as wav

from voice_input.config import load_config
from voice_input.whisper_model import WhisperModel


def main():
    parser = argparse.ArgumentParser(description="Transcribe a WAV file using voice-input config")
    parser.add_argument("wav_file", help="Path to 16 kHz mono WAV file")
    args = parser.parse_args()

    config_path = os.path.expanduser("~/.config/voice-input/config.toml")
    cfg = load_config(config_path)

    model = WhisperModel(cfg["model"], overrides=cfg.get("whisper", {}))
    rate, data = wav.read(args.wav_file)
    text = model.transcribe(data)
    print(text)


if __name__ == "__main__":
    main()
