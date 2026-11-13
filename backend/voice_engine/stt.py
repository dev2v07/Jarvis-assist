"""Speech-recognition adapters used by Jarvis.

The live microphone loop keeps Vosk as a lightweight fallback for now. This
module provides the faster-whisper path for push-to-talk and future streaming
integration without coupling the router or UI to a concrete STT package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


class FasterWhisperRecognizer:
    """Lazy local faster-whisper recognizer; no model is loaded at import time."""

    def __init__(self, model_name: str = "small", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model: Any | None = None

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def _load(self):
        if self._model is None:
            if not self.available():
                raise RuntimeError("faster-whisper не установлен")
            from faster_whisper import WhisperModel

            compute_type = "int8" if self.device == "cpu" else "float16"
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=compute_type,
                local_files_only=True,
            )
        return self._model

    def transcribe(self, audio_path: str | Path) -> str:
        segments, _ = self._load().transcribe(
            str(audio_path), language="ru", vad_filter=True, beam_size=1
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

