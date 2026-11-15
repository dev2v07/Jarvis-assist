from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.chat_store import ChatStore
from services.voice_runtime import VoiceRuntime
from services.voice_session_manager import VoiceSessionManager


class VoiceRuntimeLifecycleTests(unittest.TestCase):
    def test_stop_drains_conversation_control_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ChatStore(Path(directory) / "state.sqlite3")
            sessions = VoiceSessionManager()
            runtime = VoiceRuntime(Path(__file__).resolve().parents[1], store, sessions)
            # Reproduce the post-stop sentinel without opening a real audio
            # device in a unit test.
            runtime._enabled = True
            runtime._conversation_queue.put(None)
            runtime.stop()
            self.assertFalse(runtime.status()["enabled"])
            self.assertFalse(runtime.status()["conversation_worker"])
            self.assertEqual(runtime.status()["conversation_queue_size"], 0)


if __name__ == "__main__":
    unittest.main()
