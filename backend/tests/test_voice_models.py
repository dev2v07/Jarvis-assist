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

    def test_fish_profiles_are_registered(self):
        status = self.manager.status()
        self.assertEqual(status["models"][1]["model_id"], "fish_jarvis")
        self.assertEqual(status["models"][2]["model_id"], "fish_dean")

    def test_selection_and_unknown_model(self):
        self.assertEqual(self.manager.select("fish_jarvis")["selected_id"], "fish_jarvis")
        self.assertEqual(self.manager.select("fish_dean")["selected_id"], "fish_dean")
        with self.assertRaises(ValueError):
            self.manager.select("missing")


if __name__ == "__main__":
    unittest.main()
