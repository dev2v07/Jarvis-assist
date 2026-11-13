"""Small streaming Silero VAD adapter with a deterministic RMS fallback."""

from __future__ import annotations

import importlib.util
import struct
from typing import Any


class SileroVAD:
    def __init__(self, sample_rate: int = 16000, threshold: float = 0.45):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self._model: Any | None = None

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("silero_vad") is not None

    def _load(self):
        if self._model is None:
            if not self.available():
                return None
            from silero_vad import load_silero_vad

            self._model = load_silero_vad()
        return self._model

    def is_speech(self, pcm16: bytes) -> bool:
        if not pcm16:
            return False
        model = self._load()
        if model is not None:
            import torch

            samples = torch.tensor(
                struct.unpack("<%dh" % (len(pcm16) // 2), pcm16), dtype=torch.float32
            ) / 32768.0
            with torch.no_grad():
                probability = float(model(samples, self.sample_rate).item())
            return probability >= self.threshold

        # Conservative fallback used only when the optional VAD package is absent.
        samples = struct.unpack("<%dh" % (len(pcm16) // 2), pcm16)
        rms = (sum(value * value for value in samples) / max(1, len(samples))) ** 0.5
        return rms >= 450.0
