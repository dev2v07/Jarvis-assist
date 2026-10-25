from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Dict, List

import requests
from cachetools import TTLCache

from config import RETRY_BACKOFF_SECONDS, SEARCH_CACHE_TTL
from utils.logging_setup import get_logger


logger = get_logger("jarvis.llm")

_cache = TTLCache(maxsize=128, ttl=SEARCH_CACHE_TTL)


# ---------------------------------------------------------
# SYSTEM PROMPT JARVIS
# ---------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """
Ты Jarvis — персональный AI ассистент пользователя.

Твои правила:

• Отвечай кратко
• Отвечай по делу
• Используй русский язык
• Не выдумывай факты
• Если пользователь просит действие — объясни что будет сделано

Ты работаешь внутри системы агентов.
"""


class LocalLLMService:

    def __init__(self, overrides: dict[str, str] | None = None):

        self._overrides = overrides or {}

        self.backend_name = self.provider

    # -----------------------------------------------------

    def _getenv(self, key: str, default: str = "") -> str:

        return str(self._overrides.get(key, os.getenv(key, default)))

    # -----------------------------------------------------
    # PROVIDER
    # -----------------------------------------------------

    @property
    def provider(self) -> str:

        return self._getenv("HEL_LLM_PROVIDER", "ollama").lower()

    # -----------------------------------------------------
    # OLLAMA
    # -----------------------------------------------------

    @property
    def ollama_base_url(self) -> str:

        return self._getenv("HEL_OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    @property
    def ollama_model(self) -> str:

        return self._getenv("HEL_OLLAMA_MODEL", "qwen2.5:7b-q4_K_M")

    # -----------------------------------------------------
    # OPENAI
    # -----------------------------------------------------

    @property
    def openai_base_url(self) -> str:

        return self._getenv("HEL_OPENAI_BASE_URL", "https://api.openai.com/v1")

    @property
    def openai_api_key(self) -> str:

        return self._getenv("HEL_OPENAI_API_KEY", "")

    @property
    def openai_model(self) -> str:

        return self._getenv("HEL_OPENAI_MODEL", "gpt-4o-mini")

    @property
    def openai_temperature(self) -> float:

        return float(self._getenv("HEL_OPENAI_TEMPERATURE", "0.2"))

    # -----------------------------------------------------

    @property
    def request_timeout(self) -> int:

        return int(self._getenv("HEL_LLM_REQUEST_TIMEOUT", "45"))

    @property
    def max_retries(self) -> int:

        return int(self._getenv("HEL_LLM_MAX_RETRIES", "2"))

    # -----------------------------------------------------

    def reload(self):

        self._overrides = {}

        self.backend_name = self.provider

        _cache.clear()

    def reload_config(self):

        self.reload()

    # -----------------------------------------------------
    # CHAT
    # -----------------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str | None = None,
    ) -> str:

        self.backend_name = self.provider

        if not system_prompt:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        key = str(
            (
                self.backend_name,
                system_prompt,
                tuple((m["role"], m["content"]) for m in messages),
            )
        )

        if key in _cache:

            return _cache[key]

        try:

            if self.backend_name == "ollama":

                response = await asyncio.to_thread(
                    self._with_retries,
                    self._chat_ollama,
                    messages,
                    system_prompt,
                )

            elif self.backend_name in {"openai", "openai_compatible"}:

                response = await asyncio.to_thread(
                    self._with_retries,
                    self._chat_openai_compatible,
                    messages,
                    system_prompt,
                )

            else:

                response = self._chat_stub(messages, system_prompt)

        except Exception:

            logger.exception(
                "llm_provider_failed",
                extra={"provider": self.backend_name},
            )

            response = self._chat_stub(messages, system_prompt)

        _cache[key] = response

        return response

    # -----------------------------------------------------
    # PLAN STEPS
    # -----------------------------------------------------

    async def plan_steps(self, goal: str, mode: str, context: str) -> list[str]:

        prompt = (
            "Верни JSON массив из 3-5 коротких шагов. "
            f"Цель: {goal}. "
            f"Режим: {mode}. "
            f"Контекст: {context}"
        )

        try:

            raw = await self.chat(
                [{"role": "user", "content": prompt}],
                system_prompt="Return JSON only.",
            )

            data = self._extract_json_array(raw)

            if isinstance(data, list):

                return [str(x).strip() for x in data if str(x).strip()][:5]

        except Exception:

            logger.exception("llm_plan_steps_failed")

        return []

    # -----------------------------------------------------
    # RETRY
    # -----------------------------------------------------

    def _with_retries(self, fn, messages, system_prompt):

        attempts = max(1, self.max_retries + 1)

        last_error = None

        for attempt in range(1, attempts + 1):

            try:

                logger.info(
                    "llm_request",
                    extra={
                        "provider": self.backend_name,
                        "attempt": attempt,
                    },
                )

                return fn(messages, system_prompt)

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "llm_retry",
                    extra={"attempt": attempt},
                )

                if attempt < attempts:

                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        raise RuntimeError("LLM provider failed") from last_error

    # -----------------------------------------------------
    # OLLAMA
    # -----------------------------------------------------

    def _chat_ollama(self, messages, system_prompt):

        payload_messages = list(messages)

        if system_prompt:

            payload_messages = [
                {"role": "system", "content": system_prompt}
            ] + payload_messages

        response = requests.post(
            f"{self.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": self.ollama_model,
                "messages": payload_messages,
                "stream": False,
                "options": {
                    "temperature": 0.2
                },
            },
            timeout=self.request_timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("message", {}).get("content") or ""

    # -----------------------------------------------------
    # OPENAI
    # -----------------------------------------------------

    def _chat_openai_compatible(self, messages, system_prompt):

        if not self.openai_api_key:

            raise RuntimeError("HEL_OPENAI_API_KEY not set")

        payload_messages = list(messages)

        if system_prompt:

            payload_messages = [
                {"role": "system", "content": system_prompt}
            ] + payload_messages

        response = requests.post(
            f"{self.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}"
            },
            json={
                "model": self.openai_model,
                "messages": payload_messages,
                "temperature": self.openai_temperature,
            },
            timeout=self.request_timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]

    # -----------------------------------------------------
    # STUB
    # -----------------------------------------------------

    def _chat_stub(self, messages, system_prompt):

        text = messages[-1]["content"] if messages else ""

        return (
            "Jarvis (stub режим)\n\n"
            f"Получен запрос: {text[:500]}"
        )

    # -----------------------------------------------------

    def _extract_json_array(self, raw: str):

        raw = raw.strip()

        try:

            return json.loads(raw)

        except json.JSONDecodeError:

            start = raw.find("[")
            end = raw.rfind("]")

            if start != -1 and end != -1:

                return json.loads(raw[start : end + 1])

            raise


llm_service = LocalLLMService()