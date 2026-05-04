from __future__ import annotations

import logging
import os

from anthropic import AsyncAnthropic

from bot.services.search_service import search_service

logger = logging.getLogger(__name__)

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "Search the web for current information. Use this when you need up-to-date facts or recent events.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up"
            }
        },
        "required": ["query"]
    }
}


SYSTEM_PROMPT = """Ты — дружелюбный помощник. Всегда отвечай на русском языке.

Форматирование (КРИТИЧЕСКИ ВАЖНО):
- НЕ используй списки смартфонами (- или •)
- НЕ используй заголовки (#)
- Пиши ПРОСТЫМ текстом с абзацами
- Между каждым абзацем делай ПУСТУЮ строку (двойной перенос)
- Каждый абзац — это 1-3 предложения

Пример:
Первый абзац описывает что-то. Здесь может быть несколько предложений.

Второй абзац описывает другое. Тоже несколько предложений для читаемости.

Третий абзац завершает мысль."""


class AIService:
    def __init__(self) -> None:
        import sys
        all_keys = list(os.environ.keys())
        print(f"ALL ENV KEYS: {all_keys}", file=sys.stderr)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        print(f"API KEY PRESENT: {bool(api_key)}", file=sys.stderr)
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        self._client = AsyncAnthropic(api_key=api_key)

    async def get_response(self, user_message: str, conversation_history: list | None = None) -> str:
        messages: list = list(conversation_history) if conversation_history else []
        messages.append({"role": "user", "content": user_message})

        try:
            logger.info(f"Sending message to Claude: {user_message[:50]}...")
            response = await self._client.beta.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=[WEB_SEARCH_TOOL],  # type: ignore[list-item]
            )

            if response.stop_reason == "tool_use":
                tool_use = next((c for c in response.content if c.type == "tool_use"), None)
                if tool_use:
                    logger.info(f"Claude calling tool: {tool_use.name}")
                    result = search_service.search(str(tool_use.input.get("query", "")))

                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result
                        }]
                    })

                    response = await self._client.beta.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=1024,
                        system=SYSTEM_PROMPT,
                        messages=messages,
                        tools=[WEB_SEARCH_TOOL],  # type: ignore[list-item]
                    )

            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    logger.info(f"Claude response: {text[:50]}...")
                    return text
            return "Не удалось получить ответ"
        except Exception as e:
            logger.error(f"Error getting AI response: {e}", exc_info=True)
            return f"Sorry, I'm having trouble answering right now. ({type(e).__name__}: {e})"


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service