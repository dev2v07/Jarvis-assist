from __future__ import annotations

import unittest

from core.contracts import (
    AgentResult,
    ProviderStatus,
    RequestContext,
    RuntimeEvent,
    new_request_context,
)


class CoreContractsTests(unittest.TestCase):
    def test_request_context_round_trip_is_json_compatible(self) -> None:
        context = new_request_context(
            session_id="session-1",
            client="web",
            platform="browser",
            metadata={"device_id": "browser-1"},
        )

        restored = RequestContext.from_dict(context.to_dict())

        self.assertEqual(restored, context)
        self.assertTrue(context.request_id)

    def test_runtime_event_round_trip_preserves_envelope(self) -> None:
        event = RuntimeEvent(
            event_type="task.progress",
            source="planner",
            request_id="request-1",
            payload={"step": 1, "total": 3},
        )

        restored = RuntimeEvent.from_dict(event.to_dict())

        self.assertEqual(restored, event)
        self.assertEqual(restored.schema_version, 1)

    def test_agent_result_factories_normalize_success_and_failure(self) -> None:
        success = AgentResult.success(
            "request-1",
            "voice",
            "Готово",
            data={"format": "wav"},
            duration_ms=12,
        )
        failure = AgentResult.failure("request-1", "vision", "Камера недоступна")

        self.assertEqual(success.status, "completed")
        self.assertEqual(success.to_dict()["data"]["format"], "wav")
        self.assertEqual(failure.status, "failed")
        self.assertEqual(failure.error, "Камера недоступна")

    def test_provider_status_rejects_negative_latency(self) -> None:
        with self.assertRaises(ValueError):
            ProviderStatus("ollama", True, latency_ms=-1)


if __name__ == "__main__":
    unittest.main()
