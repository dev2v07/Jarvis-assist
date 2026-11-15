from __future__ import annotations

import unittest
from pathlib import Path

from services.knowledge_index_service import KnowledgeIndexService


class KnowledgeIntegrityTests(unittest.TestCase):
    def test_partial_audio_is_reported_as_partial_not_ready(self) -> None:
        result = KnowledgeIndexService(Path(__file__).resolve().parents[1]).integrity()
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertTrue(result["roots"]["offline_knowledge"].endswith("offline_knowledge"))
        self.assertEqual(result["audio_groups"]["lessons"]["status"], "AUDIO_PARTIAL")
        self.assertEqual(result["audio_groups"]["offline"]["status"], "AUDIO_READY")


if __name__ == "__main__":
    unittest.main()
