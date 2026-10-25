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

_cache = TTLCache(maxsize=128, ttl=SEARCH_CACHE_TTL)
logger = get_logger('hel.llm')


class LocalLLMService:
    def __init__(self, overrides: dict[str, str] | None = None):
        self._overrides = overrides or {}
        self.backend_name = self.provider

    def _getenv(self, key: str, default: str = '') -> str:
        return str(self._overrides.get(key, os.getenv(key, default)))

    @property
    def provider(self) -> str:
        return self._getenv('HEL_LLM_PROVIDER', 'stub').lower()

    @property
    def ollama_base_url(self) -> str:
        return self._getenv('HEL_OLLAMA_BASE_URL', 'http://127.0.0.1:11434')

    @property
    def ollama_model(self) -> str:
        return self._getenv('HEL_OLLAMA_MODEL', 'qwen2.5:7b-q4_K_M')

    @property
    def openai_base_url(self) -> str:
        return self._getenv('HEL_OPENAI_BASE_URL', 'https://api.openai.com/v1')

    @property
    def openai_api_key(self) -> str:
        return self._getenv('HEL_OPENAI_API_KEY', '')

    @property
    def openai_model(self) -> str:
        return self._getenv('HEL_OPENAI_MODEL', 'gpt-4o-mini')

    @property
    def openai_temperature(self) -> float:
        return float(self._getenv('HEL_OPENAI_TEMPERATURE', '0.2'))

    @property
    def request_timeout(self) -> int:
        return int(self._getenv('HEL_LLM_REQUEST_TIMEOUT', '45'))

    @property
    def max_retries(self) -> int:
        return int(self._getenv('HEL_LLM_MAX_RETRIES', '2'))

    def reload(self):
        self._overrides = {}
        self.backend_name = self.provider
        _cache.clear()

    def reload_config(self):
        self.reload()

    async def chat(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        self.backend_name = self.provider
        key = str((self.backend_name, system_prompt, tuple((m['role'], m['content']) for m in messages)))
        if key in _cache:
            return _cache[key]

        try:
            if self.backend_name == 'ollama':
                response = await asyncio.to_thread(self._with_retries, self._chat_ollama, messages, system_prompt)
            elif self.backend_name in {'openai', 'openai_compatible'}:
                response = await asyncio.to_thread(self._with_retries, self._chat_openai_compatible, messages, system_prompt)
            else:
                response = self._chat_stub(messages, system_prompt)
        except Exception:
            logger.exception('llm_provider_failed_falling_back', extra={'event': 'llm_provider_failed', 'provider': self.backend_name})
            response = self._chat_stub(messages, system_prompt)

        _cache[key] = response
        return response

    async def plan_steps(self, goal: str, mode: str, context: str) -> list[str]:
        prompt = (
            'Верни только JSON-массив из 3-5 коротких шагов на русском языке. '
            'Шаги должны быть исполнимыми для локального desktop AI-ассистента. '
            f'Режим: {mode}. Контекст: {context}. Цель: {goal}'
        )
        try:
            raw = await self.chat([{'role': 'user', 'content': prompt}], system_prompt='Return JSON only.')
            data = self._extract_json_array(raw)
            if isinstance(data, list):
                steps = [str(item).strip() for item in data if str(item).strip()]
                if steps:
                    return steps[:5]
        except Exception:
            logger.exception('llm_plan_steps_failed', extra={'event': 'llm_plan_steps_failed', 'provider': self.backend_name})
        return []


    def test_connection_sync(self) -> dict:
        try:
            return asyncio.run(self.test_connection())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.test_connection())
            finally:
                loop.close()

    async def test_connection_with_overrides(self, overrides: dict[str, str]) -> dict:
        previous = self._overrides
        try:
            self._overrides = overrides
            self.backend_name = self.provider
            return await self.test_connection()
        finally:
            self._overrides = previous
            self.backend_name = self.provider

    async def test_connection(self) -> dict:
        self.reload()
        provider = self.backend_name
        if provider == 'stub':
            return {'ok': True, 'provider': 'stub', 'message': 'Используется встроенный stub-провайдер.'}
        try:
            if provider == 'ollama':
                data = await asyncio.to_thread(self._test_ollama)
                return {'ok': True, 'provider': provider, 'message': f"Ollama доступен, модель {data.get('model', self.ollama_model)}"}
            if provider in {'openai', 'openai_compatible'}:
                data = await asyncio.to_thread(self._test_openai)
                return {'ok': True, 'provider': provider, 'message': f"OpenAI-compatible API доступен, модель {data.get('model', self.openai_model)}"}
            return {'ok': False, 'provider': provider, 'message': f'Неизвестный провайдер: {provider}'}
        except Exception as exc:
            logger.exception('llm_test_failed', extra={'event': 'llm_test_failed', 'provider': provider})
            return {'ok': False, 'provider': provider, 'message': str(exc)}

    def _chat_stub(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        user_text = messages[-1]['content'] if messages else ''
        if system_prompt and 'JSON' in system_prompt.upper():
            return '[]'
        return (
            'Локальный ответ ядра Хель. '
            + f'Получена задача: {user_text[:500]}\n\n'
            + 'Это базовый ответ-заглушка; подключите Ollama/OpenAI-совместимый backend для расширенной генерации.'
        )

    def _with_retries(self, fn, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        attempts = max(1, self.max_retries + 1)
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                logger.info('llm_request', extra={'event': 'llm_request', 'provider': self.backend_name, 'attempt': attempt})
                return fn(messages, system_prompt)
            except Exception as exc:
                last_error = exc
                logger.warning('llm_request_retry', extra={'event': 'llm_request_retry', 'provider': self.backend_name, 'attempt': attempt})
                if attempt < attempts:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        raise RuntimeError(f'LLM provider failed after {attempts} attempts') from last_error

    def _chat_ollama(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        payload_messages = list(messages)
        if system_prompt:
            payload_messages = [{'role': 'system', 'content': system_prompt}] + payload_messages
        response = requests.post(
            f'{self.ollama_base_url.rstrip("/")}/api/chat',
            json={'model': self.ollama_model, 'messages': payload_messages, 'stream': False},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('message', {}).get('content') or data.get('response') or ''

    def _chat_openai_compatible(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        if not self.openai_api_key:
            raise RuntimeError('HEL_OPENAI_API_KEY is not set')
        payload_messages = list(messages)
        if system_prompt:
            payload_messages = [{'role': 'system', 'content': system_prompt}] + payload_messages
        response = requests.post(
            f'{self.openai_base_url.rstrip("/")}/chat/completions',
            headers={'Authorization': f'Bearer {self.openai_api_key}'},
            json={
                'model': self.openai_model,
                'messages': payload_messages,
                'temperature': self.openai_temperature,
            },
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get('choices') or []
        if not choices:
            return ''
        return choices[0].get('message', {}).get('content', '')

    def _test_ollama(self) -> dict:
        response = requests.get(f'{self.ollama_base_url.rstrip("/")}/api/tags', timeout=min(self.request_timeout, 10))
        response.raise_for_status()
        data = response.json()
        models = data.get('models') or []
        found = next((m for m in models if m.get('name') == self.ollama_model), None)
        return {'model': found.get('name') if found else self.ollama_model, 'models_found': len(models)}

    def _test_openai(self) -> dict:
        if not self.openai_api_key:
            raise RuntimeError('HEL_OPENAI_API_KEY is not set')
        response = requests.get(
            f'{self.openai_base_url.rstrip("/")}/models',
            headers={'Authorization': f'Bearer {self.openai_api_key}'},
            timeout=min(self.request_timeout, 10),
        )
        response.raise_for_status()
        data = response.json()
        return {'model': self.openai_model, 'models_found': len(data.get('data') or [])}

    def _extract_json_array(self, raw: str):
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start:end + 1])
            raise


llm_service = LocalLLMService()
