from __future__ import annotations

import json
import unittest
from pathlib import Path

from knowledge.apply_bible_physical_consolidation import MANIFEST_PATH, path_map, verify_manifest


class BiblePhysicalConsolidationTests(unittest.TestCase):
    def test_current_manifest_is_verified_and_plan_is_non_destructive(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual([], verify_manifest(manifest))
        self.assertTrue(all(source.exists() or target.exists() for source, target in path_map()))
        self.assertTrue(all(target.is_dir() for _, target in path_map()))
        self.assertTrue(all(not source.is_dir() for source, _ in path_map()))
        self.assertTrue((Path(__file__).resolve().parents[2] / "data/archive/bible_legacy_sources_20261115").is_dir())

    def test_user_facing_library_is_single_catalog_view(self):
        root = Path(__file__).resolve().parents[2]
        library = root / "data" / "Bible" / "library"
        catalog = json.loads((root / "data" / "Bible" / "index" / "library_catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["record_count"], 7233)
        self.assertEqual(json.loads((library / "CPU" / "catalog.json").read_text(encoding="utf-8"))["record_count"], 52)
        self.assertEqual(json.loads((library / "Computer" / "catalog.json").read_text(encoding="utf-8"))["record_count"], 384)
        self.assertEqual(json.loads((library / "Responses" / "catalog.json").read_text(encoding="utf-8"))["record_count"], 229)
        self.assertFalse((root / "data" / "Bible" / "knowledge").exists())
        self.assertFalse((root / "data" / "Bible" / "sources").exists())


if __name__ == "__main__":
    unittest.main()
