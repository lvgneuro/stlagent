from __future__ import annotations

import json
import logging
import os

from anthropic import AsyncAnthropic

from bot.database import db
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


FACT_EXTRACTION_PROMPT = """Извлеки факты о пользователе из этого разговора. 
Верни JSON массив где каждый элемент это объект с полями: fact_type, fact_value, context.

Примеры fact_type:
- name - имя пользователя
- location - местоположение
- job - работа/профессия
- interests - интересы
- preferences - предпочтения
- family - семья
- health - здоровье
- other - другое

Верни ТОЛЬКО JSON массив, без пояснений."""

CONTEXT_PROMPT = """Используй эту информацию о пользователе для персонализации ответа:

Факты о пользователе:
{facts}

Контекст из прошлых разговоров:
{context}

Отвечай на основе этой информации."""


class AIService:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client = AsyncAnthropic(api_key=api_key) if api_key else None

    def is_configured(self) -> bool:
        return self._client is not None

    async def get_response(
        self,
        user_message: str,
        conversation_history: list | None = None,
        user_id: int = 0,
    ) -> str:
        if not self._client:
            return "⚠️ Бот не настроен: отсутствует ANTHROPIC_API_KEY"
        
        if user_id:
            user_facts = await db.get_user_facts(user_id)
            context_messages = await db.search_context(user_id, user_message)
            
            context_parts = []
            if user_facts:
                context_parts.append("Факты о пользователе:\n" + "\n".join(f"- {k}: {v}" for k, v in user_facts.items()))
            
            if context_messages:
                context_parts.append("Из прошлых разговоров:\n" + "\n".join(f"- {m[:150]}" for m in context_messages[-3:]))
            
            search_indicators = ["погода", "новости", "что new", "сегодня", "сейчас", "2024", "2025", "2026", "курс", "цена", "кто такой", "что такое", "найти", "узнать"]
            needs_search = any(word in user_message.lower() for word in search_indicators)
            logger.info(f"Message: {user_message}, needs_search: {needs_search}")
            
            search_result = ""
            if needs_search:
                try:
                    search_result = search_service.search(user_message)
                    logger.info(f"Search result: {search_result[:200]}...")
                except Exception as e:
                    logger.warning(f"Search failed: {e}")
            
            system_with_context = SYSTEM_PROMPT
            if search_result:
                system_with_context += f"\n\nАктуальная информация из интернета:\n{search_result[:1500]}"
            
            if context_parts:
                system_with_context += "\n\n" + CONTEXT_PROMPT.format(
                    facts=context_parts[0] if len(context_parts) > 0 else "Нет данных",
                    context=context_parts[1] if len(context_parts) > 1 else "Нет данных"
                )
            
            logger.info(f"User facts: {user_facts}, context: {len(context_messages)} messages")
        else:
            system_with_context = SYSTEM_PROMPT
        
        messages = [{"role": "user", "content": user_message}]

        try:
            logger.info(f"Sending message to Claude: {user_message[:50]}...")
            response = await self._client.beta.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_with_context,
                messages=messages,
            )

            logger.info(f"Response stop_reason: {response.stop_reason}")
            
            text = None
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break
            
            if text and user_id:
                await self._extract_and_save_facts(user_message, text, user_id)
            
            return text if text else "Не удалось получить ответ"
        except Exception as e:
            logger.error(f"Error getting AI response: {e}", exc_info=True)
            return f"Sorry, I'm having trouble answering right now. ({type(e).__name__}: {e})"

    async def _extract_and_save_facts(self, user_message: str, bot_response: str, user_id: int) -> None:
        logger.info(f"Extracting facts for user {user_id}: {user_message[:50]}...")
        try:
            extraction_prompt = f"""Извлеки факты о пользователе из этого разговора.

Примеры фактов которые нужно искать:
- name: имя пользователя (например: "Вячеслав", "Анна")
- color: любимый цвет (например: "зеленый", "синий")
- interest: интересы, хобби
- location: местоположение, город
- job: работа, профессия
- other: любые другие значимые факты

Разговор:
Пользователь: {user_message[:500]}
Бот: {bot_response[:500]}

Верни JSON массив объектов, например:
[{{"fact_type": "name", "fact_value": "Иван"}}, {{"fact_type": "color", "fact_value": "синий"}}]

Если фактов нет - верни пустой массив []."""

            response = await self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": extraction_prompt}]
            )

            text = response.content[0].text if response.content else ""
            logger.info(f"Extracted text: {text[:200]}...")
            
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            try:
                facts = json.loads(text.strip())
                logger.info(f"Parsed facts: {facts}")
                if isinstance(facts, list):
                    for fact in facts:
                        if "fact_type" in fact and "fact_value" in fact:
                            await db.save_fact(
                                user_id=user_id,
                                fact_type=fact["fact_type"],
                                fact_value=fact["fact_value"],
                                context=f"{user_message[:100]} -> {bot_response[:100]}",
                            )
                logger.info(f"Saved {len(facts) if isinstance(facts, list) else 0} facts for user {user_id}")
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse facts JSON: {text[:200]}")
        except Exception as e:
            logger.error(f"Error extracting facts: {e}")


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service