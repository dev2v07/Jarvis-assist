from __future__ import annotations

import asyncio
import unittest

from core.agent_base import Agent
from core.message_bus import MessageBus


class LifecycleAgent(Agent):
    async def on_start(self):
        await asyncio.Event().wait()

    async def handle_message(self, msg):
        return None


class AgentLifecycleTests(unittest.TestCase):
    def test_stop_cancels_main_and_lifecycle_tasks(self):
        async def scenario():
            agent = LifecycleAgent("lifecycle-test", MessageBus())
            agent.start()
            await asyncio.sleep(0)
            main_task = agent._task
            lifecycle_task = agent._lifecycle_task
            await agent.stop()
            self.assertFalse(agent._running)
            self.assertIsNone(agent._task)
            self.assertIsNone(agent._lifecycle_task)
            self.assertTrue(main_task.done())
            self.assertTrue(lifecycle_task.done())

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
