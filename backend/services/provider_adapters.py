"""Provider adapter contract and safe HTTP implementations.

Adapters return a normalized :class:`ProviderResponse`.  They never log or
include API keys in exceptions.  Claude, Codex and FreeLLMAPI are represented
as explicit not-configured adapters until their credentials and API contracts
are supplied.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import requests
import json


class ProviderError(RuntimeError):
    """Base error safe to show to the runtime without raw HTTP payloads."""


class ProviderConfigurationError(ProviderError):
    def __init__(self, provider: str, missing: list[str]) -> None:
        self.provider = provider
        self.missing = tuple(missing)
        fields = ", ".join(self.missing) or "provider configuration"
        super().__init__(f"{provider} is not configured: {fields}")


class ProviderRequestError(ProviderError):
    def __init__(self, provider: str, reason: str, status_code: int | None = None) -> None:
        self.provider = provider
        self.reason = reason
        self.status_code = status_code
        suffix = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"{provider} request failed: {reason}{suffix}")


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "text": self.text,
            "usage": dict(self.usage),
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
        }


def normalize_provider_name(provider: str | None) -> str:
    value = str(provider or "stub").strip().lower().replace("-", "_")
    return {
        "free_llm_api": "freellmapi",
        "free_llmapi": "freellmapi",
        "openai_codex": "codex",
    }.get(value, value or "stub")


class ProviderAdapter(ABC):
    provider_name: str
    implemented = True

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = dict(config or {})

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def configuration_status(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> ProviderResponse:
        raise NotImplementedError

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ):
        """Yield text deltas; adapters without native streaming yield once."""
        response = self.chat(messages, system_prompt)
        if response.text:
            yield response.text

    @staticmethod
    def _messages(messages: list[dict[str, str]], system_prompt: str | None) -> list[dict[str, str]]:
        prepared = list(messages)
        if system_prompt:
            prepared.insert(0, {"role": "system", "content": system_prompt})
        return prepared

    @staticmethod
    def _usage(data: Mapping[str, Any]) -> dict[str, Any]:
        usage = data.get("usage")
        if isinstance(usage, Mapping):
            return dict(usage)
        keys = ("prompt_eval_count", "eval_count", "prompt_tokens", "completion_tokens")
        return {key: data[key] for key in keys if key in data}


class _HttpAdapter(ProviderAdapter):
    def _post_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = requests.post(url, **kwargs)
        except requests.RequestException as exc:
            # Do not stringify the exception: URLs or third-party payloads may
            # contain user data.  The provider and stable error type are enough.
            raise ProviderRequestError(self.provider_name, type(exc).__name__) from exc

        if not 200 <= response.status_code < 300:
            raise ProviderRequestError(self.provider_name, "non_success_response", response.status_code)

        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise ProviderRequestError(self.provider_name, "invalid_json_response") from exc

        if not isinstance(data, dict):
            raise ProviderRequestError(self.provider_name, "invalid_response_shape")
        return data


class OllamaAdapter(_HttpAdapter):
    provider_name = "ollama"

    @property
    def keep_alive(self) -> str | int:
        """Return Ollama's duration or numeric indefinite keep-alive value."""
        raw = str(self.config.get("HEL_OLLAMA_KEEP_ALIVE") or "15m").strip()
        return -1 if raw == "-1" else raw

    @property
    def base_url(self) -> str:
        return str(self.config.get("HEL_OLLAMA_BASE_URL") or self.config.get("base_url") or "").strip()

    @property
    def model(self) -> str:
        return str(self.config.get("HEL_OLLAMA_MODEL") or self.config.get("model") or "").strip()

    @property
    def timeout(self) -> int:
        return int(self.config.get("HEL_LLM_REQUEST_TIMEOUT") or self.config.get("timeout") or 45)

    def configuration_status(self) -> dict[str, Any]:
        missing = [
            key
            for key, value in (("HEL_OLLAMA_BASE_URL", self.base_url), ("HEL_OLLAMA_MODEL", self.model))
            if not value
        ]
        return {
            "provider": self.provider_name,
            "model": self.model or None,
            "configured": not missing,
            "implemented": True,
            "missing": missing,
        }

    def chat(self, messages: list[dict[str, str]], system_prompt: str | None = None) -> ProviderResponse:
        status = self.configuration_status()
        if not status["configured"]:
            raise ProviderConfigurationError(self.provider_name, status["missing"])

        options = {
            "temperature": float(self.config.get("HEL_OPENAI_TEMPERATURE") or 0.2),
        }
        think = str(self.config.get("HEL_OLLAMA_THINK", "false")).lower() in {"1", "true", "yes", "on"}
        num_predict = self.config.get("HEL_OLLAMA_NUM_PREDICT")
        if num_predict:
            try:
                options["num_predict"] = max(16, min(256, int(num_predict)))
            except (TypeError, ValueError):
                pass
        data = self._post_json(
            f"{self.base_url.rstrip('/')}/api/chat",
            json={
                "model": self.model,
                "messages": self._messages(messages, system_prompt),
                "stream": False,
                "think": think,
                "keep_alive": self.keep_alive,
                "options": options,
            },
            timeout=self.timeout,
        )
        text = str((data.get("message") or {}).get("content") or "")
        return ProviderResponse(
            provider=self.provider_name,
            model=self.model,
            text=text,
            usage=self._usage(data),
            finish_reason=data.get("done_reason"),
        )

    def stream_chat(self, messages: list[dict[str, str]], system_prompt: str | None = None):
        status = self.configuration_status()
        if not status["configured"]:
            raise ProviderConfigurationError(self.provider_name, status["missing"])
        options = {
            "temperature": float(self.config.get("HEL_OPENAI_TEMPERATURE") or 0.2),
        }
        think = str(self.config.get("HEL_OLLAMA_THINK", "false")).lower() in {"1", "true", "yes", "on"}
        num_predict = self.config.get("HEL_OLLAMA_NUM_PREDICT")
        if num_predict:
            try:
                options["num_predict"] = max(16, min(256, int(num_predict)))
            except (TypeError, ValueError):
                pass
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.model,
                    "messages": self._messages(messages, system_prompt),
                    "stream": True,
                    "think": think,
                    "keep_alive": self.keep_alive,
                    "options": options,
                },
                timeout=self.timeout,
                stream=True,
            )
            if not 200 <= response.status_code < 300:
                raise ProviderRequestError(self.provider_name, "non_success_response", response.status_code)
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (TypeError, ValueError) as exc:
                    raise ProviderRequestError(self.provider_name, "invalid_stream_response") from exc
                delta = str((data.get("message") or {}).get("content") or "")
                if delta:
                    yield delta
                if data.get("done"):
                    break
        except requests.RequestException as exc:
            raise ProviderRequestError(self.provider_name, type(exc).__name__) from exc


class OpenAICompatibleAdapter(_HttpAdapter):
    provider_name = "openai_compatible"

    @property
    def api_key(self) -> str:
        return str(self.config.get("HEL_OPENAI_API_KEY") or self.config.get("api_key") or "").strip()

    @property
    def base_url(self) -> str:
        return str(self.config.get("HEL_OPENAI_BASE_URL") or self.config.get("base_url") or "").strip()

    @property
    def model(self) -> str:
        return str(self.config.get("HEL_OPENAI_MODEL") or self.config.get("model") or "").strip()

    @property
    def timeout(self) -> int:
        return int(self.config.get("HEL_LLM_REQUEST_TIMEOUT") or self.config.get("timeout") or 45)

    def configuration_status(self) -> dict[str, Any]:
        missing = [
            key
            for key, value in (
                ("HEL_OPENAI_API_KEY", self.api_key),
                ("HEL_OPENAI_BASE_URL", self.base_url),
                ("HEL_OPENAI_MODEL", self.model),
            )
            if not value
        ]
        return {
            "provider": self.provider_name,
            "model": self.model or None,
            "configured": not missing,
            "implemented": True,
            "missing": missing,
        }

    def chat(self, messages: list[dict[str, str]], system_prompt: str | None = None) -> ProviderResponse:
        status = self.configuration_status()
        if not status["configured"]:
            raise ProviderConfigurationError(self.provider_name, status["missing"])

        data = self._post_json(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": self._messages(messages, system_prompt),
                "temperature": float(self.config.get("HEL_OPENAI_TEMPERATURE") or 0.2),
            },
            timeout=self.timeout,
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise ProviderRequestError(self.provider_name, "missing_choices")
        message = choices[0].get("message") or {}
        return ProviderResponse(
            provider=self.provider_name,
            model=self.model,
            text=str(message.get("content") or ""),
            usage=self._usage(data),
            finish_reason=choices[0].get("finish_reason"),
        )

    def stream_chat(self, messages: list[dict[str, str]], system_prompt: str | None = None):
        """Stream OpenAI-compatible SSE deltas so remote replies can be spoken sooner."""
        status = self.configuration_status()
        if not status["configured"]:
            raise ProviderConfigurationError(self.provider_name, status["missing"])
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": self._messages(messages, system_prompt),
                    "temperature": float(self.config.get("HEL_OPENAI_TEMPERATURE") or 0.2),
                    "stream": True,
                },
                timeout=self.timeout,
                stream=True,
            )
            if not 200 <= response.status_code < 300:
                raise ProviderRequestError(self.provider_name, "non_success_response", response.status_code)
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                text = str(line).strip()
                if text.startswith("data:"):
                    text = text[5:].strip()
                if text == "[DONE]":
                    break
                try:
                    data = json.loads(text)
                except (TypeError, ValueError) as exc:
                    raise ProviderRequestError(self.provider_name, "invalid_stream_response") from exc
                choices = data.get("choices") or []
                if choices and isinstance(choices[0], Mapping):
                    delta = choices[0].get("delta") or {}
                    content = str(delta.get("content") or "") if isinstance(delta, Mapping) else ""
                    if content:
                        yield content
        except requests.RequestException as exc:
            raise ProviderRequestError(self.provider_name, type(exc).__name__) from exc


class DeepSeekAdapter(OpenAICompatibleAdapter):
    """DeepSeek's official OpenAI-compatible chat API."""

    provider_name = "deepseek"

    @property
    def api_key(self) -> str:
        return str(self.config.get("HEL_DEEPSEEK_API_KEY") or "").strip()

    @property
    def base_url(self) -> str:
        return str(self.config.get("HEL_DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()

    @property
    def model(self) -> str:
        return str(self.config.get("HEL_DEEPSEEK_MODEL") or "deepseek-flash").strip()

    def configuration_status(self) -> dict[str, Any]:
        missing = [
            key for key, value in (
                ("HEL_DEEPSEEK_API_KEY", self.api_key),
                ("HEL_DEEPSEEK_BASE_URL", self.base_url),
                ("HEL_DEEPSEEK_MODEL", self.model),
            ) if not value
        ]
        return {
            "provider": self.provider_name,
            "model": self.model or None,
            "configured": not missing,
            "implemented": True,
            "missing": missing,
        }


class StubAdapter(ProviderAdapter):
    provider_name = "stub"

    @property
    def model(self) -> str:
        return "built-in"

    def configuration_status(self) -> dict[str, Any]:
        return {"provider": self.provider_name, "model": self.model, "configured": True, "implemented": True, "missing": []}

    def chat(self, messages: list[dict[str, str]], system_prompt: str | None = None) -> ProviderResponse:
        text = messages[-1].get("content", "") if messages else ""
        return ProviderResponse(self.provider_name, self.model, f"Jarvis (stub режим)\n\nПолучен запрос: {text[:500]}")


class NotConfiguredAdapter(ProviderAdapter):
    implemented = False

    def __init__(self, provider_name: str, missing: list[str], model: str = "") -> None:
        super().__init__()
        self.provider_name = provider_name
        self._missing = tuple(missing)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def configuration_status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model or None,
            "configured": False,
            "implemented": False,
            "missing": list(self._missing),
            "error_code": "adapter_not_configured",
        }

    def chat(self, messages: list[dict[str, str]], system_prompt: str | None = None) -> ProviderResponse:
        raise ProviderConfigurationError(self.provider_name, list(self._missing))


class CodexAdapter(NotConfiguredAdapter):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        super().__init__("codex", ["HEL_CODEX_API_KEY", "HEL_CODEX_MODEL"])


class ClaudeAdapter(NotConfiguredAdapter):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        super().__init__("claude", ["HEL_ANTHROPIC_API_KEY", "HEL_ANTHROPIC_MODEL"])


class FreeLLMAPIAdapter(OpenAICompatibleAdapter):
    """FreeLLMAPI's /v1 endpoint follows the OpenAI-compatible contract."""

    provider_name = "freellmapi"

    @property
    def api_key(self) -> str:
        return str(self.config.get("HEL_FREELLMAPI_API_KEY") or self.config.get("api_key") or "").strip()

    @property
    def base_url(self) -> str:
        return str(self.config.get("HEL_FREELLMAPI_BASE_URL") or self.config.get("base_url") or "").strip()

    @property
    def model(self) -> str:
        return str(self.config.get("HEL_FREELLMAPI_MODEL") or self.config.get("model") or "").strip()

    def configuration_status(self) -> dict[str, Any]:
        missing = [
            key
            for key, value in (
                ("HEL_FREELLMAPI_API_KEY", self.api_key),
                ("HEL_FREELLMAPI_BASE_URL", self.base_url),
                ("HEL_FREELLMAPI_MODEL", self.model),
            )
            if not value
        ]
        return {
            "provider": self.provider_name,
            "model": self.model or None,
            "configured": not missing,
            "implemented": True,
            "missing": missing,
        }


SUPPORTED_PROVIDERS = ("stub", "ollama", "openai", "openai_compatible", "deepseek", "codex", "claude", "freellmapi")


def build_provider_adapter(provider: str | None, config: Mapping[str, Any] | None = None) -> ProviderAdapter:
    name = normalize_provider_name(provider)
    values = dict(config or {})
    if name == "stub":
        return StubAdapter(values)
    if name == "ollama":
        return OllamaAdapter(values)
    if name in {"openai", "openai_compatible"}:
        adapter = OpenAICompatibleAdapter(values)
        if name == "openai":
            adapter.provider_name = "openai"
        return adapter
    if name == "deepseek":
        return DeepSeekAdapter(values)
    if name == "codex":
        return CodexAdapter(values)
    if name == "claude":
        return ClaudeAdapter(values)
    if name == "freellmapi":
        return FreeLLMAPIAdapter(values)
    raise ValueError(f"Unsupported provider: {name}")
