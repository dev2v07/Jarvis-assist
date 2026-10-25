from __future__ import annotations

import uuid
import asyncio
from pathlib import Path

import pyautogui
import pytesseract
from PIL import Image

from core.agent_base import Agent

# optional AI vision
try:
    from services.awesome_chat import awesome_chat
    AI_VISION_AVAILABLE = True
except Exception:
    AI_VISION_AVAILABLE = False


WORKSPACE = Path("workspace")
WORKSPACE.mkdir(exist_ok=True)


class VisionAgent(Agent):

    def __init__(self, bus):
        super().__init__("vision", bus)

    # ------------------------------------------------
    # MAIN ENTRY
    # ------------------------------------------------

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        request_id = payload["original_msg_id"]
        step = payload.get("step", "")
        target = payload.get("target")

        artifact = None

        try:

            result, artifact = await self.process_vision(step, target)

        except Exception as e:

            result = f"VisionAgent error: {str(e)}"

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": request_id,
                    "result": result,
                    "artifact": artifact,
                }
            }
        )

    # ------------------------------------------------
    # CORE LOGIC
    # ------------------------------------------------

    async def process_vision(self, step: str, target: str | None):

        step = step.lower()

        # ----------------------------------
        # SCREENSHOT
        # ----------------------------------

        if "скрин" in step or "screenshot" in step:

            filename = WORKSPACE / f"screenshot_{uuid.uuid4().hex[:6]}.png"

            screenshot = pyautogui.screenshot()

            screenshot.save(filename)

            return (
                f"Скриншот сохранён: {filename}",
                {
                    "type": "image",
                    "name": "screenshot",
                    "path": str(filename)
                }
            )

        # ----------------------------------
        # OCR SCREEN
        # ----------------------------------

        if "прочитай экран" in step or "текст на экране" in step:

            screenshot = pyautogui.screenshot()

            text = pytesseract.image_to_string(screenshot).strip()

            if not text:
                return "Текст на экране не найден", None

            return f"Найден текст:\n{text[:1200]}", None

        # ----------------------------------
        # OCR IMAGE
        # ----------------------------------

        if target:

            img = Image.open(target)

            text = pytesseract.image_to_string(img)

            if text.strip():

                return f"Текст на изображении:\n{text[:1200]}", None

            # ----------------------------------
            # AI IMAGE DESCRIPTION
            # ----------------------------------

            if AI_VISION_AVAILABLE:

                try:

                    result = await asyncio.to_thread(
                        awesome_chat.image_to_text,
                        "nlpconnect/vit-gpt2-image-captioning",
                        target
                    )

                    caption = result.get("generated_text")

                    if caption:
                        return f"Описание изображения:\n{caption}", None

                except Exception:
                    pass

            return "Текст на изображении не найден", None

        # ----------------------------------
        # SCREEN ANALYSIS
        # ----------------------------------

        if "что на экране" in step or "analyze screen" in step:

            filename = WORKSPACE / f"screen_{uuid.uuid4().hex[:6]}.png"

            screenshot = pyautogui.screenshot()

            screenshot.save(filename)

            if AI_VISION_AVAILABLE:

                try:

                    result = await asyncio.to_thread(
                        awesome_chat.image_to_text,
                        "nlpconnect/vit-gpt2-image-captioning",
                        str(filename)
                    )

                    caption = result.get("generated_text")

                    return f"На экране похоже изображено:\n{caption}", None

                except Exception:
                    pass

            return f"Скриншот сделан: {filename}", None

        # ----------------------------------

        return "VisionAgent получил команду, но не распознал действие", None