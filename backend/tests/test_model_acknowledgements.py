from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.voice_runtime import VoiceRuntime
from voice_engine.model_acknowledgements import (
    MODEL_ACKNOWLEDGEMENTS,
    model_acknowledgement_dir,
)


class ModelAcknowledgementTests(unittest.TestCase):
    def test_catalog_contains_requested_variants(self) -> None:
        self.assertEqual(len(MODEL_ACKNOWLEDGEMENTS), 7)
        self.assertEqual(len({filename for _text, filename in MODEL_ACKNOWLEDGEMENTS}), 7)

    def test_runtime_uses_available_cached_wav_without_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ack_dir = model_acknowledgement_dir(root)
            ack_dir.mkdir(parents=True)
            (ack_dir / "model_ack_01.wav").write_bytes(b"test")
            runtime = VoiceRuntime.__new__(VoiceRuntime)
            runtime.base_dir = root / "backend"
            runtime._last_model_ack = None
            runtime._say_wav = lambda path: setattr(runtime, "_played_ack", Path(path).name)
            with patch("random.choice", side_effect=lambda values: values[0]):
                runtime._play_model_acknowledgement()
            self.assertEqual(runtime._played_ack, "model_ack_01.wav")


if __name__ == "__main__":
    unittest.main()
