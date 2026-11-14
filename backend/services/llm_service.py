from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Dict, List

import requests
from cachetools import TTLCache

from config import OLLAMA_MODEL, RETRY_BACKOFF_SECONDS, SEARCH_CACHE_TTL, read_runtime_config
from services.provider_adapters import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRequestError,
    build_provider_adapter,
)
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
        self._provider_cooldown_until = 0.0

    # -----------------------------------------------------

    def _getenv(self, key: str, default: str = "") -> str:
        if key in self._overrides:
            return str(self._overrides[key])
        value = os.getenv(key)
        if value is not None and str(value).strip():
            return str(value)
        runtime = read_runtime_config(mask_secrets=False)
        return str(runtime.get(key, default))

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

        return self._getenv("HEL_OLLAMA_MODEL", OLLAMA_MODEL)

    @property
    def ollama_think(self) -> bool:
        return self._getenv("HEL_OLLAMA_THINK", "false").strip().lower() in {"1", "true", "yes", "on"}

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

    @property
    def deepseek_base_url(self) -> str:
        return self._getenv("HEL_DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @property
    def deepseek_api_key(self) -> str:
        return self._getenv("HEL_DEEPSEEK_API_KEY", "")

    @property
    def deepseek_model(self) -> str:
        return self._getenv("HEL_DEEPSEEK_MODEL", "deepseek-flash")

    def _provider_config(self) -> dict[str, str]:
        """Build adapter config without logging or serializing credentials."""

        return {
            "HEL_OLLAMA_BASE_URL": self.ollama_base_url,
            "HEL_OLLAMA_MODEL": self.ollama_model,
            "HEL_OLLAMA_THINK": str(self.ollama_think).lower(),
            "HEL_OPENAI_BASE_URL": self.openai_base_url,
            "HEL_OPENAI_MODEL": self.openai_model,
            "HEL_OPENAI_API_KEY": self.openai_api_key,
            "HEL_OPENAI_TEMPERATURE": str(self.openai_temperature),
            "HEL_DEEPSEEK_BASE_URL": self.deepseek_base_url,
            "HEL_DEEPSEEK_MODEL": self.deepseek_model,
            "HEL_DEEPSEEK_API_KEY": self.deepseek_api_key,
            "HEL_LLM_REQUEST_TIMEOUT": str(self.request_timeout),
            # Keep spoken replies short by default; users can override this
            # without changing the runtime code.
            "HEL_OLLAMA_NUM_PREDICT": self._getenv("HEL_OLLAMA_NUM_PREDICT", "64"),
            "HEL_CODEX_API_KEY": self._getenv("HEL_CODEX_API_KEY"),
            "HEL_CODEX_MODEL": self._getenv("HEL_CODEX_MODEL"),
            "HEL_ANTHROPIC_API_KEY": self._getenv("HEL_ANTHROPIC_API_KEY"),
            "HEL_ANTHROPIC_MODEL": self._getenv("HEL_ANTHROPIC_MODEL"),
            "HEL_FREELLMAPI_API_KEY": self._getenv("HEL_FREELLMAPI_API_KEY"),
            "HEL_FREELLMAPI_BASE_URL": self._getenv("HEL_FREELLMAPI_BASE_URL"),
            "HEL_FREELLMAPI_MODEL": self._getenv("HEL_FREELLMAPI_MODEL"),
        }

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

            adapter = build_provider_adapter(
                self.backend_name,
                self._provider_config(),
            )
            provider_response = await asyncio.to_thread(
                self._with_retries,
                adapter.chat,
                messages,
                system_prompt,
            )
            response = provider_response.text

        except ProviderConfigurationError as exc:

            # Configuration errors must not silently become a stub response.
            # Only stable provider/field names are returned; credentials never
            # enter logs or user-facing error text.
            logger.warning(
                "llm_provider_not_configured",
                extra={"provider": exc.provider},
            )
            missing = ", ".join(exc.missing)
            response = f"Провайдер {exc.provider} не настроен. Укажите: {missing}."

        except ProviderError:

            logger.exception(
                "llm_provider_failed",
                extra={"provider": self.backend_name},
            )

            response = self._chat_stub(messages, system_prompt)

        except Exception:

            logger.exception(
                "llm_provider_failed",
                extra={"provider": self.backend_name},
            )

            response = self._chat_stub(messages, system_prompt)

        _cache[key] = response

        return response

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str | None = None,
    ):
        """Yield provider deltas without buffering the whole Ollama response."""
        self.backend_name = self.provider
        system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        adapter = build_provider_adapter(self.backend_name, self._provider_config())
        queue: asyncio.Queue[str | BaseException | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def produce():
            try:
                for delta in adapter.stream_chat(messages, system_prompt):
                    asyncio.run_coroutine_threadsafe(queue.put(str(delta)), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)
            except BaseException as error:
                asyncio.run_coroutine_threadsafe(queue.put(error), loop)

        task = asyncio.create_task(asyncio.to_thread(produce))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            if not task.done():
                task.cancel()

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

        # A stopped local Ollama is a normal desktop state, not a transient
        # server error. Retrying a refused TCP connection makes every chat
        # request feel frozen and needlessly blocks the agent pipeline.
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

                if isinstance(exc, ProviderConfigurationError):
                    # A missing key/model is deterministic; retrying it only
                    # delays the actionable configuration error.
                    raise

                if isinstance(exc, ProviderRequestError) and exc.status_code is not None and exc.status_code < 500:
                    # Invalid keys, rejected models and malformed requests are
                    # deterministic; retrying them freezes the desktop UI.
                    raise

                logger.warning(
                    "llm_retry",
                    extra={"attempt": attempt},
                )

                if isinstance(exc, requests.exceptions.ConnectionError):
                    raise RuntimeError(
                        f"Провайдер {self.backend_name} недоступен; проверьте его запуск и настройки."
                    ) from exc

                if attempt < attempts:

                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        raise RuntimeError("LLM provider failed") from last_error

    # -----------------------------------------------------
    # OLLAMA
    # -----------------------------------------------------

    def _chat_ollama(self, messages, system_prompt):
        adapter = build_provider_adapter("ollama", self._provider_config())
        return adapter.chat(messages, system_prompt).text

    # -----------------------------------------------------
    # OPENAI
    # -----------------------------------------------------

    def _chat_openai_compatible(self, messages, system_prompt):
        adapter = build_provider_adapter("openai_compatible", self._provider_config())
        return adapter.chat(messages, system_prompt).text

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

    async def test_connection_with_overrides(self, overrides: dict[str, str]) -> dict[str, object]:
        """Probe one provider using temporary config without exposing secrets."""

        service = LocalLLMService(overrides=overrides)
        provider = service.provider
        try:
            adapter = build_provider_adapter(provider, service._provider_config())
            result = await asyncio.to_thread(
                service._with_retries,
                adapter.chat,
                [{"role": "user", "content": "ping"}],
                "Return a short health-check response.",
            )
            return {
                "ok": True,
                "provider": provider,
                "model": result.model,
                "response": result.text,
            }
        except ProviderConfigurationError as exc:
            return {
                "ok": False,
                "provider": exc.provider,
                "error_code": "not_configured",
                "missing": list(exc.missing),
            }
        except ProviderRequestError as exc:
            messages = {
                401: "DeepSeek отклонил API-ключ. Проверьте ключ в настройках.",
                402: "DeepSeek принял ключ, но на аккаунте недостаточно баланса или кредитов.",
                403: "DeepSeek запретил запрос для этого ключа или модели.",
                429: "DeepSeek временно ограничил частоту запросов. Попробуйте позже.",
            }
            return {
                "ok": False,
                "provider": exc.provider,
                "error_code": "provider_http_error",
                "status_code": exc.status_code,
                "message": messages.get(exc.status_code, "Провайдер вернул ошибку HTTP."),
            }
        except ProviderError as exc:
            logger.warning(
                "llm_provider_connection_test_failed",
                extra={"provider": provider, "error_code": type(exc).__name__},
            )
            return {
                "ok": False,
                "provider": provider,
                "error_code": "provider_request_failed",
                "message": "Провайдер недоступен или вернул некорректный ответ.",
            }
        except Exception:
            logger.exception(
                "llm_provider_connection_test_failed",
                extra={"provider": provider},
            )
            return {
                "ok": False,
                "provider": provider,
                "error_code": "provider_test_failed",
                "message": "Не удалось проверить провайдер.",
            }

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
