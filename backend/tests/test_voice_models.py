import unittest
from pathlib import Path

from voice_engine.voice_models import VoiceModelManager


class VoiceModelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.manager = VoiceModelManager(Path(__file__).resolve().parents[1])

    def test_jarvis_is_first_and_default(self):
        status = self.manager.status()
        self.assertEqual(status["selected_id"], "jarvis")
        self.assertEqual(status["models"][0]["model_id"], "jarvis")
        self.assertTrue(status["models"][0]["default"])
        self.assertFalse(status["models"][0]["ready"])

    def test_kesha_checkpoint_is_available(self):
        status = self.manager.status()
        kesha = status["models"][1]
        self.assertEqual(kesha["model_id"], "kesha")
        self.assertFalse(kesha["ready"])
        self.assertTrue(kesha["available"])
        self.assertTrue(status["silero_checkpoint_exists"])

    def test_selection_and_unknown_model(self):
        self.assertEqual(self.manager.select("kesha")["selected_id"], "kesha")
        self.assertEqual(self.manager.select("fish_jarvis")["selected_id"], "fish_jarvis")
        with self.assertRaises(ValueError):
            self.manager.select("missing")


if __name__ == "__main__":
    unittest.main()
