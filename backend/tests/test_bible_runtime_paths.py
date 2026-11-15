from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.daw_control_service import DawControlService
from services.knowledge_search_service import KnowledgeSearchService
from services.local_response_service import LocalResponseService
from services.mixing_service import MixingService
from services.programming_mentor_service import ProgrammingMentorService
from services.voice_production_service import VoiceProductionService


class BibleRuntimePathTests(unittest.TestCase):
    def test_mutable_knowledge_state_is_owned_by_bible_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = root / "backend"
            backend.mkdir()

            local = LocalResponseService(backend)
            search = KnowledgeSearchService(backend, local)
            voice = VoiceProductionService(backend)
            programming = ProgrammingMentorService(backend)
            daw = DawControlService(backend)

            runtime_root = root / "data" / "Bible" / "index" / "runtime"
            self.assertEqual(local.state_path.parent, runtime_root)
            self.assertEqual(search.variant_state_path.parent, runtime_root)
            self.assertEqual(voice.sessions_path.parent, runtime_root)
            self.assertEqual(programming.progress_path.parent, runtime_root)
            self.assertEqual(daw.snapshot_root.parent, runtime_root / "daw")
            preview_source = root / "data" / "Bible" / "materials" / "knowledge3" / "demo.wav"
            self.assertEqual(MixingService._preview_root(preview_source), runtime_root / "mixing" / "renders")


if __name__ == "__main__":
    unittest.main()
