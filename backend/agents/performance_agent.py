from __future__ import annotations

import uuid
import psutil

from core.agent_base import Agent

try:
    import GPUtil
except:
    GPUtil = None


class PerformanceAgent(Agent):

    def __init__(self, bus):
        super().__init__("performance", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]
        request_id = payload["original_msg_id"]

        try:

            # -------------------------
            # CPU
            # -------------------------

            cpu_load = psutil.cpu_percent(interval=0.5)

            # -------------------------
            # RAM
            # -------------------------

            ram = psutil.virtual_memory()
            ram_used = ram.percent

            # -------------------------
            # DISK
            # -------------------------

            disk = psutil.disk_usage("/")
            disk_used = disk.percent

            # -------------------------
            # GPU
            # -------------------------

            gpu_load = None

            if GPUtil:

                gpus = GPUtil.getGPUs()

                if gpus:
                    gpu_load = round(gpus[0].load * 100)

            # -------------------------
            # RESULT
            # -------------------------

            result = (
                f"CPU: {cpu_load}%\n"
                f"RAM: {ram_used}%\n"
                f"DISK: {disk_used}%"
            )

            if gpu_load is not None:
                result += f"\nGPU: {gpu_load}%"
            else:
                result += "\nGPU: не обнаружен"

        except Exception as e:

            result = f"PerformanceAgent error: {str(e)}"

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": request_id,
                    "result": result
                },
            },
        )