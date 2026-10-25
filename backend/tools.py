import ollama
from config import OLLAMA_MODEL


class LLMService:

    async def chat(self, messages, system_prompt=None):

        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages
        )

        return response["message"]["content"]


llm_service = LLMService()