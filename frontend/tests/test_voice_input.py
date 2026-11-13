import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice_input import merge_transcript


class VoiceInputTests(unittest.TestCase):
    def test_appends_to_existing_draft(self):
        text, position = merge_transcript("Привет", "как дела", position=6)
        self.assertEqual(text, "Привет как дела")
        self.assertEqual(position, len(text))

    def test_inserts_at_cursor_without_overwriting_draft(self):
        text, position = merge_transcript("Привет мир", "мой", position=7)
        self.assertEqual(text, "Привет мой мир")
        self.assertEqual(position, 11)

    def test_replaces_selection(self):
        text, position = merge_transcript(
            "старый текст", "новый", position=12,
            selection_start=0, selection_end=12,
        )
        self.assertEqual(text, "новый")
        self.assertEqual(position, 5)

    def test_empty_transcript_is_noop(self):
        text, position = merge_transcript("черновик", "", position=3)
        self.assertEqual(text, "черновик")
        self.assertEqual(position, 3)


if __name__ == "__main__":
    unittest.main()
