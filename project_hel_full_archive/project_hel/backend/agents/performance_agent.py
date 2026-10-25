from __future__ import annotations
import uuid
from core.agent_base import Agent
from utils.tooling import monitor_performance

class PerformanceAgent(Agent):
    def __init__(self, bus):
        super().__init__('performance', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return
        perf = monitor_performance()
        result = f"Показатели системы: CPU {perf['cpu_percent']}%, RAM {perf['ram_percent']}%, Disk {perf['disk_percent']}%"
        await self.bus.send('critic', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'critic',
            'type': 'critique',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
