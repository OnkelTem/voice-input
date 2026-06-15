import os
import tomllib


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
