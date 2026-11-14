from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.llm_service import LocalLLMService
from services.provider_adapters import (
    ProviderConfigurationError,
    ProviderRequestError,
    build_provider_adapter,
)


def response(payload: dict, status_code: int = 200) -> SimpleNamespace:
    return SimpleNamespace(status_code=status_code, json=lambda: payload)


def stream_response(lines: list[str], status_code: int = 200) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=status_code,
        iter_lines=lambda decode_unicode=True: iter(lines),
    )


class ProviderAdapterTests(unittest.TestCase):
    def test_ollama_adapter_maps_native_response(self) -> None:
        adapter = build_provider_adapter(
            "ollama",
            {
                "HEL_OLLAMA_BASE_URL": "http://ollama.test",
                "HEL_OLLAMA_MODEL": "jarvis-local",
            },
        )

        with patch("services.provider_adapters.requests.post", return_value=response({
            "message": {"content": "локальный ответ"},
            "done_reason": "stop",
            "eval_count": 7,
        })) as post:
            result = adapter.chat([{"role": "user", "content": "Привет"}], "Система")

        self.assertEqual(result.provider, "ollama")
        self.assertEqual(result.text, "локальный ответ")
        self.assertEqual(result.usage["eval_count"], 7)
        self.assertEqual(post.call_args.args[0], "http://ollama.test/api/chat")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertFalse(payload["stream"])

    def test_openai_compatible_adapter_maps_chat_completion(self) -> None:
        adapter = build_provider_adapter(
            "openai",
            {
                "HEL_OPENAI_BASE_URL": "https://provider.test/v1",
                "HEL_OPENAI_MODEL": "model-a",
                "HEL_OPENAI_API_KEY": "secret-key-never-logged",
            },
        )

        with patch("services.provider_adapters.requests.post", return_value=response({
            "choices": [{
                "message": {"content": "ответ API"},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 11},
        })) as post:
            result = adapter.chat([{"role": "user", "content": "Тест"}])

        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.text, "ответ API")
        self.assertEqual(result.usage["total_tokens"], 11)
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer secret-key-never-logged",
        )
        self.assertNotIn("secret-key-never-logged", str(result.to_dict()))

    def test_deepseek_uses_dedicated_openai_compatible_configuration(self) -> None:
        adapter = build_provider_adapter("deepseek", {
            "HEL_DEEPSEEK_BASE_URL": "https://api.deepseek.test",
            "HEL_DEEPSEEK_MODEL": "deepseek-flash",
            "HEL_DEEPSEEK_API_KEY": "deepseek-secret",
        })
        with patch("services.provider_adapters.requests.post", return_value=response({
            "choices": [{"message": {"content": "ответ DeepSeek"}, "finish_reason": "stop"}],
        })) as post:
            result = adapter.chat([{"role": "user", "content": "Привет"}], "Ты Jarvis")
        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.text, "ответ DeepSeek")
        self.assertEqual(post.call_args.args[0], "https://api.deepseek.test/chat/completions")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "deepseek-flash")

    def test_ollama_stream_adapter_yields_deltas(self) -> None:
        adapter = build_provider_adapter(
            "ollama",
            {
                "HEL_OLLAMA_BASE_URL": "http://ollama.test",
                "HEL_OLLAMA_MODEL": "jarvis-local",
            },
        )
        stream = stream_response([
            '{"message":{"content":"При"},"done":false}',
            '{"message":{"content":"вет"},"done":true}',
        ])
        with patch("services.provider_adapters.requests.post", return_value=stream) as post:
            result = list(adapter.stream_chat([{"role": "user", "content": "Привет"}]))
        self.assertEqual(result, ["При", "вет"])
        self.assertTrue(post.call_args.kwargs["stream"])

    def test_unconfigured_provider_adapters_fail_honestly(self) -> None:
        for provider in ("codex", "claude", "freellmapi"):
            adapter = build_provider_adapter(provider, {})
            status = adapter.configuration_status()

            self.assertFalse(status["configured"])
            self.assertFalse(status["implemented"])
            with self.assertRaises(ProviderConfigurationError) as raised:
                adapter.chat([])

            self.assertEqual(raised.exception.provider, provider)
            self.assertNotIn("secret", str(raised.exception))

    def test_local_llm_service_uses_adapter_without_changing_return_contract(self) -> None:
        service = LocalLLMService(
            overrides={
                "HEL_LLM_PROVIDER": "ollama",
                "HEL_OLLAMA_BASE_URL": "http://ollama.test",
                "HEL_OLLAMA_MODEL": "test-model",
            }
        )

        with patch("services.provider_adapters.requests.post", return_value=response({
            "message": {"content": "через adapter"},
        })):
            result = asyncio.run(service.chat([
                {"role": "user", "content": "adapter smoke"},
            ]))

        self.assertEqual(result, "через adapter")

    def test_configuration_error_is_not_silently_replaced_with_stub(self) -> None:
        service = LocalLLMService(
            overrides={
                "HEL_LLM_PROVIDER": "claude",
            }
        )

        result = asyncio.run(service.chat([
            {"role": "user", "content": "проверка"},
        ]))

        self.assertIn("Провайдер claude не настроен", result)
        self.assertNotIn("stub режим", result)

    def test_provider_4xx_is_not_retried(self) -> None:
        service = LocalLLMService(overrides={
            "HEL_LLM_PROVIDER": "deepseek",
            "HEL_DEEPSEEK_API_KEY": "bad-key",
        })
        with self.assertRaises(ProviderRequestError):
            service._with_retries(
                lambda messages, prompt: (_ for _ in ()).throw(ProviderRequestError("deepseek", "unauthorized", 401)),
                [],
                "health",
            )


if __name__ == "__main__":
    unittest.main()
