from __future__ import annotations
import time
from pathlib import Path
import numpy as np
from typing import Any
from cffi import FFI

_HERE = Path(__file__).parent

ffi = FFI()

ffi.cdef("""
    struct whisper_context_params {
        bool use_gpu;
        bool flash_attn;
        int  gpu_device;
        bool dtw_token_timestamps;
        int  dtw_aheads_preset;
        int  dtw_n_top;
        struct {
            size_t n_heads;
            const struct { int n_text_layer; int n_head; } * heads;
        } dtw_aheads;
        size_t dtw_mem_size;
    };

    struct whisper_full_params {
        int   strategy;
        int   n_threads;
        int   n_max_text_ctx;
        int   offset_ms;
        int   duration_ms;
        bool  translate;
        bool  no_context;
        bool  no_timestamps;
        bool  single_segment;
        bool  print_special;
        bool  print_progress;
        bool  print_realtime;
        bool  print_timestamps;
        bool  token_timestamps;
        float thold_pt;
        float thold_ptsum;
        int   max_len;
        bool  split_on_word;
        int   max_tokens;
        bool  debug_mode;
        int   audio_ctx;
        bool  tdrz_enable;
        const char * suppress_regex;
        const char * initial_prompt;
        bool  carry_initial_prompt;
        const int * prompt_tokens;
        int   prompt_n_tokens;
        const char * language;
        bool  detect_language;
        bool  suppress_blank;
        bool  suppress_nst;
        float temperature;
        float max_initial_ts;
        float length_penalty;
        float temperature_inc;
        float entropy_thold;
        float logprob_thold;
        float no_speech_thold;
        struct { int best_of; } greedy;
        struct { int beam_size; float patience; } beam_search;
        void * new_segment_callback;
        void * new_segment_callback_user_data;
        void * progress_callback;
        void * progress_callback_user_data;
        void * encoder_begin_callback;
        void * encoder_begin_callback_user_data;
        void * abort_callback;
        void * abort_callback_user_data;
        void * logits_filter_callback;
        void * logits_filter_callback_user_data;
        const void * grammar_rules;
        size_t n_grammar_rules;
        size_t i_start_rule;
        float grammar_penalty;
        bool  vad;
        const char * vad_model_path;
        struct {
            float threshold;
            int   min_speech_duration_ms;
            int   min_silence_duration_ms;
            float max_speech_duration_s;
            int   speech_pad_ms;
            float samples_overlap;
        } vad_params;
    };

    struct whisper_context_params whisper_context_default_params(void);
    struct whisper_full_params *  whisper_full_default_params_by_ref(int strategy);
    struct whisper_context * whisper_init_from_file_with_params(const char * path, struct whisper_context_params params);
    int  whisper_full_ptr(struct whisper_context * ctx, struct whisper_full_params * params, const float * samples, int n_samples);
    int  whisper_full_n_segments(struct whisper_context * ctx);
    const char * whisper_full_get_segment_text(struct whisper_context * ctx, int i_segment);
    int  whisper_full_lang_id(struct whisper_context * ctx);
    int  whisper_n_text_ctx(struct whisper_context * ctx);
    void whisper_free(struct whisper_context * ctx);
    void whisper_log_set(void (*callback)(int level, const char * text, void * user_data), void * user_data);
""")

_LIB = ffi.dlopen(str(_HERE / "whisper_helper.so"))


class WhisperModel:
    _WHISPER_FIELDS = {
        "n_threads":                    "n_threads",
        "n_max_text_ctx":               "n_max_text_ctx",
        "language":                     "language",
        "temperature":                  "temperature",
        "temperature_inc":              "temperature_inc",
        "suppress_nst":                 "suppress_nst",
        "no_context":                   "no_context",
        "translate":                    "translate",
        "single_segment":               "single_segment",
        "max_len":                      "max_len",
        "split_on_word":                "split_on_word",
        "suppress_blank":               "suppress_blank",
        "no_timestamps":                "no_timestamps",
        "initial_prompt":               "initial_prompt",
        "carry_initial_prompt":         "carry_initial_prompt",
        "suppress_regex":               "suppress_regex",
        "vad":                          "vad",
        "print_special":                "print_special",
        "debug_mode":                   "debug_mode",
    }

    def __init__(self, model_path: str, log_fn=print, overrides: dict[str, Any] | None = None):
        log_fn(f"Loading whisper model: {model_path}")
        cparams = _LIB.whisper_context_default_params()
        self._ctx = _LIB.whisper_init_from_file_with_params(
            model_path.encode("utf-8"), cparams)
        if not self._ctx:
            raise RuntimeError(f"Failed to init whisper from {model_path}")
        n_text_ctx = _LIB.whisper_n_text_ctx(self._ctx)
        log_fn(f"Model loaded. n_text_ctx={n_text_ctx}")
        self._log_fn = log_fn
        self._params_ptr = _LIB.whisper_full_default_params_by_ref(0)
        self._params_ptr.n_threads = 4
        self._params_ptr.n_max_text_ctx = 224
        self._lang = ffi.new("char[]", b"auto")
        self._params_ptr.language = self._lang
        self._params_ptr.no_timestamps = True
        self._params_ptr.print_progress = False
        self._params_ptr.print_realtime = False
        self._initial_prompt = ffi.NULL
        self._params_ptr.initial_prompt = ffi.NULL
        self._suppress_regex = ffi.NULL
        self._params_ptr.suppress_regex = ffi.NULL
        if overrides:
            self._apply_overrides(overrides)

        @ffi.callback("void(int, const char *, void *)")
        def _whisper_log_cb(level, text, user_data):
            level_names = {0: "NONE", 1: "DEBUG", 2: "INFO", 3: "WARN", 4: "ERROR", 5: "CONT"}
            lname = level_names.get(level, str(level))
            msg = ffi.string(text).decode("utf-8", errors="replace").rstrip()
            if msg:
                self._log_fn(f"[whisper.{lname}] {msg}")
        self._log_callback = _whisper_log_cb
        _LIB.whisper_log_set(self._log_callback, ffi.NULL)

    def _apply_overrides(self, overrides: dict[str, Any]):
        for key, value in overrides.items():
            field = self._WHISPER_FIELDS.get(key)
            if field is None:
                self._log_fn(f"  whisper: unknown option '{key}'")
                continue
            self._log_fn(f"  whisper: {key}={value}")
            if field == "language":
                if not value or value == "auto":
                    self._lang = ffi.new("char[]", b"auto")
                else:
                    self._lang = ffi.new("char[]", value.encode("utf-8"))
                self._params_ptr.language = self._lang
            elif field == "initial_prompt":
                if value:
                    self._initial_prompt = ffi.new("char[]", value.encode("utf-8"))
                else:
                    self._initial_prompt = ffi.NULL
                self._params_ptr.initial_prompt = self._initial_prompt
            elif field == "suppress_regex":
                if value:
                    self._suppress_regex = ffi.new("char[]", value.encode("utf-8"))
                else:
                    self._suppress_regex = ffi.NULL
                self._params_ptr.suppress_regex = self._suppress_regex
            elif isinstance(value, bool):
                setattr(self._params_ptr, field, value)
            elif isinstance(value, int):
                setattr(self._params_ptr, field, value)
            elif isinstance(value, float):
                setattr(self._params_ptr, field, value)
            else:
                self._log_fn(f"Unsupported type for {key}: {type(value).__name__}")

    def transcribe(self, samples: np.ndarray) -> str:
        # Normalize audio: int16 → float32 [-1,1]; float32 → use as-is
        if samples.dtype == np.int16:
            audio = samples.astype(np.float32) / 32768.0
        elif samples.dtype == np.float32:
            audio = samples.astype(np.float32)
        else:
            audio = samples.astype(np.float32) / 32768.0
        audio = audio.ravel()

        self._log_fn(
            f"whisper_full: language={ffi.string(self._params_ptr.language).decode()}, "
            f"n_threads={self._params_ptr.n_threads}, n_max_text_ctx={self._params_ptr.n_max_text_ctx}, "
            f"temperature={self._params_ptr.temperature}, temperature_inc={self._params_ptr.temperature_inc}, "
            f"strategy={self._params_ptr.strategy}"
        )
        t0 = time.monotonic()
        ptr = ffi.from_buffer("float[]", audio)
        ret = _LIB.whisper_full_ptr(self._ctx, self._params_ptr, ptr, len(audio))
        if ret != 0:
            self._log_fn(f"whisper_full returned {ret}")
            return ""
        dt = time.monotonic() - t0
        n_seg = _LIB.whisper_full_n_segments(self._ctx)
        self._log_fn(f"whisper: {n_seg} segment(s) in {dt:.2f}s")
        seg_texts = []
        for i in range(n_seg):
            seg_text = ffi.string(_LIB.whisper_full_get_segment_text(self._ctx, i)).decode("utf-8")
            seg_texts.append(seg_text)
        text = "".join(seg_texts).strip()
        lang_id = _LIB.whisper_full_lang_id(self._ctx)
        self._log_fn(f"whisper: detected lang_id={lang_id}")
        return text

    def free(self):
        _LIB.whisper_log_set(ffi.NULL, ffi.NULL)
        if self._ctx:
            _LIB.whisper_free(self._ctx)
            self._ctx = None
