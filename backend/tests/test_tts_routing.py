from __future__ import annotations

import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import voice_engine.tts as tts
from voice_engine.voice_models import VoiceModelManager


class TTSRoutingTests(unittest.TestCase):
    def test_fish_profile_does_not_fallback_to_local_xtts(self) -> None:
        class FishOnly:
            selected_id = "fish_jarvis"

            def synthesize_fish(self, text: str, profile: str = "jarvis") -> bytes:
                self.called = (text, profile)
                return b"fish-audio"

        manager = FishOnly()
        with patch.object(tts, "_voice_models", manager), patch.object(
            tts.sf, "read", return_value=([0.0, 0.0], 24000)
        ), patch.object(tts, "_play_audio") as playback, patch.object(
            tts, "_get_tts", side_effect=AssertionError("XTTS fallback must not run")
        ):
            tts.speak("тест Fish")

        self.assertEqual(manager.called, ("тест Fish", "jarvis"))
        playback.assert_called_once()

    def test_failed_fish_inference_clears_stale_ready_status(self) -> None:
        manager = VoiceModelManager(Path("."))
        with patch.object(manager, "_fish_availability", return_value=(True, "")), patch(
            "requests.post", side_effect=RuntimeError("temporary Fish failure")
        ):
            with self.assertRaises(RuntimeError):
                manager.synthesize_fish("проверка", profile="jarvis")

        status = manager.status()["selected"]
        self.assertFalse(status["ready"])
        self.assertFalse(status["inference_verified"])
        self.assertEqual(status["model_id"], "fish_jarvis")

    def test_fish_timeout_is_bounded_and_configurable(self) -> None:
        manager = VoiceModelManager(Path("."))

        class Response:
            content = b"fish-wav"

            @staticmethod
            def raise_for_status() -> None:
                return None

        with patch.object(manager, "_fish_availability", return_value=(True, "")), patch(
            "requests.post", return_value=Response()
        ) as post, patch.dict(os.environ, {"JARVIS_FISH_TTS_TIMEOUT": "999"}):
            manager.synthesize_fish("проверка", profile="jarvis")

        self.assertEqual(post.call_args.kwargs["timeout"], (8, 90))

    def test_fish_status_reports_profile_error_without_dumping_error_map(self) -> None:
        manager = VoiceModelManager(Path("."))
        with patch.object(manager, "_fish_availability", return_value=(True, "")):
            manager._fish_error["jarvis"] = "TLS handshake failed"
            status = manager.status()["selected"]

        self.assertFalse(status["ready"])
        self.assertEqual(status["message"], "TLS handshake failed")
        self.assertNotIn("jarvis", status["message"])


if __name__ == "__main__":
    unittest.main()
