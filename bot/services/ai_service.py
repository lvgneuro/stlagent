from __future__ import annotations

import logging
import os
import sys

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
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client = AsyncAnthropic(api_key=api_key) if api_key else None

    def is_configured(self) -> bool:
        return self._client is not None

    async def get_response(self, user_message: str, conversation_history: list | None = None) -> str:
        if not self._client:
            return "⚠️ Бот не настроен: отсутствует ANTHROPIC_API_KEY"
        
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

            print(f"DEBUG: stop_reason={response.stop_reason}", file=sys.stderr)
            logger.info(f"Response stop_reason: {response.stop_reason}")
            logger.info(f"Response content: {response.content}")
            
            if response.stop_reason == "tool_use":
                tool_use = next((c for c in response.content if c.type == "tool_use"), None)
                if tool_use:
                    logger.info(f"Claude calling tool: {tool_use.name}")
                    result = search_service.search(str(tool_use.input.get("query", "")))
                    logger.info(f"Search result: {result[:200]}...")

                    messages.append({"role": "assistant", "content": [{"type": block.type, "text": getattr(block, "text", "")} for block in response.content]})
                    messages.append({
                        "role": "user",
                        "tool_results": [{
                            "tool_use_id": tool_use.id,
                            "content": result
                        }]
                    })

                    response = await self._client.beta.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=1024,
                        system=SYSTEM_PROMPT,
                        messages=messages,
                    )
                    
                    logger.info(f"Second response stop_reason: {response.stop_reason}")
                    logger.info(f"Second response content: {response.content}")
                    
            for block in response.content:
                logger.info(f"Block: {block}, type: {type(block)}, attrs: {dir(block)}")
                if hasattr(block, "text"):
                    logger.info(f"Found text: {block.text}")
                    return block.text
            for block in response.content:
                logger.info(f"Block: {block}, type: {type(block)}, attrs: {dir(block)}")
                if hasattr(block, "text"):
                    logger.info(f"Found text: {block.text}")
                    return block.text
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