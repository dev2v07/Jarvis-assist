from __future__ import annotations

import asyncio
import re
import time
import uuid
import webbrowser
from html import unescape
from urllib.parse import urlparse

import requests

from config import NETWORK_MAX_RETRIES, NETWORK_REQUEST_TIMEOUT, RETRY_BACKOFF_SECONDS
from core.agent_base import Agent
from utils.logging_setup import get_logger

logger = get_logger("hel.network")


class NetworkAgent(Agent):

    def __init__(self, bus):
        super().__init__("network", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        step = payload["step"]
        target = payload.get("target") or self._extract_url(step)

        result = await asyncio.to_thread(
            self._process_request,
            step,
            target
        )

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": payload["original_msg_id"],
                    "result": result
                },
            },
        )

    # ---------------------------------------------------
    # основной обработчик
    # ---------------------------------------------------

    def _process_request(self, step: str, target: str | None) -> str:

        if not target:
            return f"Сетевой агент не нашёл URL в шаге: {step}"

        url = target if target.startswith("http") else f"https://{target}"

        step_lower = step.lower()

        # ---------------------------------------------
        # открыть сайт
        # ---------------------------------------------

        if any(word in step_lower for word in ["open", "открой", "перейди", "запусти"]):

            try:
                webbrowser.open(url)
                logger.info(
                    "browser_open",
                    extra={
                        "event": "browser_open",
                        "url": url
                    },
                )

                return f"Открываю сайт {url} в браузере"

            except Exception as e:

                logger.exception(
                    "browser_open_failed",
                    extra={"event": "browser_open_failed"}
                )

                return f"Ошибка открытия сайта: {e}"

        # ---------------------------------------------
        # определить тип запроса
        # ---------------------------------------------

        method = "HEAD" if any(
            token in step_lower
            for token in ["header", "headers", "заголов"]
        ) else "GET"

        attempts = max(1, NETWORK_MAX_RETRIES + 1)

        last_error = None

        for attempt in range(1, attempts + 1):

            try:

                logger.info(
                    "network_request",
                    extra={
                        "event": "network_request",
                        "url": url,
                        "attempt": attempt,
                    },
                )

                response = requests.request(
                    method,
                    url,
                    timeout=NETWORK_REQUEST_TIMEOUT,
                    headers={
                        "User-Agent": "ProjectHel/1.3 (+Jarvis assistant)"
                    },
                    allow_redirects=True,
                )

                response.raise_for_status()

                return self._summarize_response(method, response)

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "network_request_retry",
                    extra={
                        "event": "network_request_retry",
                        "url": url,
                        "attempt": attempt,
                    },
                )

                if attempt < attempts:

                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        logger.exception(
            "network_request_failed",
            extra={"event": "network_request_failed", "url": url},
        )

        return f"Сетевой запрос завершился ошибкой после {attempts} попыток: {last_error}"

    # ---------------------------------------------------
    # анализ ответа
    # ---------------------------------------------------

    def _summarize_response(self, method: str, response: requests.Response) -> str:

        content_type = response.headers.get("content-type", "")

        summary = [
            f"URL: {response.url}",
            f"HTTP {response.status_code}",
            f"Content-Type: {content_type or 'unknown'}",
        ]

        # HEAD запрос

        if method == "HEAD":

            important_headers = [
                "server",
                "content-length",
                "cache-control",
            ]

            headers = [
                f"{key}: {response.headers.get(key, '')}"
                for key in important_headers
                if response.headers.get(key)
            ]

            return "\n".join(summary + headers)

        # JSON

        if "application/json" in content_type:

            payload = response.json()

            preview = str(payload)[:1500]

            return "\n".join(summary + [f"JSON preview: {preview}"])

        # HTML

        text = response.text[:4000]

        title_match = re.search(
            r"<title[^>]*>(.*?)</title>",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        title = (
            unescape(title_match.group(1).strip())
            if title_match
            else "Без заголовка"
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            re.sub(r"<[^>]+>", " ", text),
        ).strip()[:1200]

        return "\n".join(summary + [
            f"Title: {title}",
            f"Content preview: {cleaned}",
        ])

    # ---------------------------------------------------
    # извлечение URL
    # ---------------------------------------------------

    def _extract_url(self, text: str) -> str | None:

        match = re.search(r"(https?://\S+)", text)

        if match:
            return match.group(1)

        for token in text.split():

            parsed = urlparse(token)

            if parsed.netloc:
                return token

            if "." in token and "/" not in token and token.count(".") >= 1:
                return token.strip(",.")

        return None