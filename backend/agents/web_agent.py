from __future__ import annotations

import uuid
import re
from playwright.async_api import async_playwright

from core.agent_base import Agent


class WebAgent(Agent):

    def __init__(self, bus):
        super().__init__("web", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        request_id = payload["original_msg_id"]
        step = payload.get("step", "")
        target = payload.get("target")

        print(f"[WEB] step: {step}")

        try:

            result = await self.run_browser_task(step, target)

        except Exception as e:

            result = f"WebAgent error: {str(e)}"

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

    async def run_browser_task(self, step: str, target: str | None):

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            step_lower = step.lower()

            # -----------------------------------
            # открыть URL
            # -----------------------------------

            if target:

                url = target if target.startswith("http") else f"https://{target}"

                await page.goto(url)

                title = await page.title()

                await browser.close()

                return f"Открыл сайт: {title}"

            # -----------------------------------
            # youtube
            # -----------------------------------

            if "youtube" in step_lower or "ютуб" in step_lower:

                await page.goto("https://youtube.com")

                title = await page.title()

                await browser.close()

                return f"YouTube открыт: {title}"

            # -----------------------------------
            # google search
            # -----------------------------------

            if "найди" in step_lower:

                query = step_lower.replace("найди", "").strip()

                await page.goto(
                    f"https://www.google.com/search?q={query}"
                )

                title = await page.title()

                await browser.close()

                return f"Google поиск: {query}"

            # -----------------------------------
            # открыть google
            # -----------------------------------

            if "google" in step_lower:

                await page.goto("https://google.com")

                title = await page.title()

                await browser.close()

                return f"Google открыт: {title}"

            # -----------------------------------
            # fallback
            # -----------------------------------

            await page.goto("https://google.com")

            title = await page.title()

            await browser.close()

            return f"Открыл браузер: {title}"