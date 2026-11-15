from __future__ import annotations

import unittest
from pathlib import Path


class LauncherContractTests(unittest.TestCase):
    """Guard the safe single-interpreter launcher contract."""

    SOURCE = (
        Path(__file__).resolve().parents[2] / "frontend" / "launch_jarvis.py"
    ).read_text(encoding="utf-8")

    def test_backend_child_uses_current_python_interpreter(self) -> None:
        self.assertIn("backend_command = [sys.executable", self.SOURCE)
        self.assertIn('env["PYTHONPATH"]', self.SOURCE)

    def test_api_endpoint_is_explicitly_configurable(self) -> None:
        self.assertIn('"JARVIS_API_BASE_URL"', self.SOURCE)
        self.assertIn('"JARVIS_API_PORT"', self.SOURCE)

    def test_incompatible_listener_is_not_force_killed(self) -> None:
        self.assertNotIn("taskkill", self.SOURCE.lower())
        self.assertIn("not stopping PID", self.SOURCE)


if __name__ == "__main__":
    unittest.main()
