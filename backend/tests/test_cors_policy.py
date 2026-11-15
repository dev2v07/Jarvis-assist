from __future__ import annotations

import unittest
from pathlib import Path


class CorsPolicyTests(unittest.TestCase):
    def test_local_file_ui_origin_is_explicitly_allowed_without_wildcard(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn('"file://"', source)
        self.assertNotIn("allow_origins=[\"*\"]", source)


if __name__ == "__main__":
    unittest.main()
