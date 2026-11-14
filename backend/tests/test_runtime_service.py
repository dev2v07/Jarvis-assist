from __future__ import annotations

import unittest
from unittest.mock import patch

from services.runtime_service import ProviderStatusService, RuntimeRegistry


class RuntimeServiceTests(unittest.TestCase):
    def test_context_and_event_use_core_contracts(self) -> None:
        registry = RuntimeRegistry(max_events=2)
        context = registry.create_context(
            session_id="session-1",
            client="mobile",
            platform="android",
        )
        event = registry.publish_event(
            event_type="task.started",
            source="mobile",
            request_id=context.request_id,
            payload={"kind": "voice"},
        )

        self.assertEqual(event.request_id, context.request_id)
        self.assertEqual(registry.list_events()[0]["payload"]["kind"], "voice")

    def test_event_journal_is_bounded(self) -> None:
        registry = RuntimeRegistry(max_events=2)
        registry.publish_event(event_type="one", source="test")
        registry.publish_event(event_type="two", source="test")
        registry.publish_event(event_type="three", source="test")

        events = registry.list_events()

        self.assertEqual([item["event_type"] for item in events], ["two", "three"])

    def test_event_journal_can_follow_one_turn(self) -> None:
        registry = RuntimeRegistry(max_events=8)
        registry.publish_event(
            event_type="turn.started",
            source="chat",
            request_id="request-1",
            payload={"chat_id": "chat-1", "turn_id": "turn-1"},
        )
        registry.publish_event(
            event_type="turn.completed",
            source="chat",
            request_id="request-2",
            payload={"chat_id": "chat-2", "turn_id": "turn-2"},
        )

        events = registry.list_events(chat_id="chat-1", turn_id="turn-1")

        self.assertEqual([item["event_type"] for item in events], ["turn.started"])

    def test_provider_snapshot_does_not_probe_when_disabled(self) -> None:
        service = ProviderStatusService()

        with patch("services.runtime_service.requests.get") as get:
            snapshot = service.snapshot(probe=False)

        get.assert_not_called()
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(len(snapshot["providers"]), 7)
        self.assertTrue(snapshot["providers"][0]["available"])


if __name__ == "__main__":
    unittest.main()
