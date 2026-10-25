from __future__ import annotations

import uuid

from core.agent_base import Agent
from voice_engine.voice_player import play_voice
from voice_engine.tts import speak


class VoiceAgent(Agent):

    def __init__(self, bus):
        super().__init__("voice", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        request_id = payload["original_msg_id"]
        step = payload.get("step", "")
        text = payload.get("text", "")

        result = await self.handle_voice(step, text)

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
                }
            }
        )

    async def handle_voice(self, step: str, text: str):

        step = step.lower()

        # --------------------------------
        # простые голосовые ответы
        # --------------------------------

        if "ok" in step:
            play_voice("ok.wav")
            return "Jarvis сказал OK"

        if "hello" in step or "привет" in step:
            play_voice("greet1.wav")
            return "Jarvis поприветствовал пользователя"

        if "thanks" in step:
            play_voice("thanks.wav")
            return "Jarvis сказал спасибо"

        # --------------------------------
        # озвучивание текста через TTS
        # --------------------------------

        if text:

            print(f"[VOICE] {text}")

            try:
                speak(text)
                return f"Jarvis сказал: {text}"
            except Exception as e:
                print("TTS error:", e)
                return "Ошибка синтеза речи"

        return "VoiceAgent обработал голосовую команду"