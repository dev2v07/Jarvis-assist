from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from services.app_server import AppServer
from services.chat_store import ChatStore
from services.runtime_service import RuntimeRegistry


class AppServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = ChatStore(Path(self.temp_dir.name) / "state.db")
        self.server = AppServer(self.store, RuntimeRegistry())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_initialize_and_thread_read_contract(self) -> None:
        initialized = asyncio.run(self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "jarvis-app-server")

        created = asyncio.run(self.server.handle({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "thread/start",
            "params": {"threadId": "thread-1", "title": "Проверка"},
        }))
        self.assertEqual(created["result"]["thread"]["id"], "thread-1")

        read = asyncio.run(self.server.handle({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "thread/read",
            "params": {"threadId": "thread-1"},
        }))
        self.assertEqual(read["result"]["thread"]["name"], "Проверка")
        self.assertEqual(read["result"]["messages"], [])

    def test_turn_start_uses_runner_and_returns_turn_id(self) -> None:
        async def scenario():
            calls = []

            async def runner(thread_id, turn_id, text, attachments):
                calls.append((thread_id, turn_id, text, attachments))
                return {"response": "ok"}

            self.server.set_turn_runner(runner)
            result = await self.server.handle({
                "jsonrpc": "2.0",
                "id": 4,
                "method": "turn/start",
                "params": {"threadId": "thread-2", "input": [{"type": "text", "text": "Привет"}]},
            })
            turn_id = result["result"]["turn"]["id"]
            self.assertEqual(result["result"]["turn"]["status"], "inProgress")
            for _ in range(20):
                if calls:
                    break
                await asyncio.sleep(0)
            self.assertEqual(calls[0][0], "thread-2")
            self.assertEqual(calls[0][1], turn_id)
            self.assertEqual(calls[0][2], "Привет")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
