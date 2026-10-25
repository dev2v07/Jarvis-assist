from __future__ import annotations
from cachetools import TTLCache
from typing import List, Dict
from config import SEARCH_CACHE_TTL

_cache = TTLCache(maxsize=128, ttl=SEARCH_CACHE_TTL)

class LocalLLMService:
    backend_name = 'local_stub'

    async def chat(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        key = str((system_prompt, tuple((m['role'], m['content']) for m in messages)))
        if key in _cache:
            return _cache[key]
        user_text = messages[-1]['content'] if messages else ''
        if system_prompt and 'JSON' in system_prompt.upper():
            response = '[]'
        else:
            response = (
                'Локальный ответ ядра Хель. '
                f'Получена задача: {user_text[:500]}\n\n'
                'Это базовый ответ-заглушка; подключите Ollama/OpenAI-совместимый backend для расширенной генерации.'
            )
        _cache[key] = response
        return response

llm_service = LocalLLMService()
