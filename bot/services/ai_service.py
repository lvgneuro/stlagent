from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from anthropic import AsyncAnthropic

from bot.database import db
from bot.services.image_service import image_service

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

Текущая дата: май 2026 года.

Важно: у тебя есть доступ к поиску актуальной информации через встроенный инструмент поиска. Используй его когда пользователь спрашивает о погоде, новостях, событиях, ценах, адресах магазинов, где что-то купить в конкретном городе.

КРИТИЧЕСКИ ВАЖНО - Твои возможности:
- КОГДА пользователь отправляет фото, ОНО СОХРАНЯЕТСЯ в базе данных
- Ты МОЖЕшь показать сохранённые фото командой /мои_фото
- Ты МОЖЕшь показать конкретное фото командой /фото 1
- Ты УМЕЕШЬ отправлять изображения обратно пользователю!

ПРАВИЛА ОТВЕТА на вопрос о фото:
- Если спрашивают "у тебя есть фото?" или "есть фото?" - СКАЖИ ДА и предложи /мои_фото
- НИКОГДА не говори что не можешь показывать фото - ТЫ МОЖЕШЬ!
- Всегда предлагай команду /мои_фото когда речь о фото

--- РЕКОМЕНДАЦИИ ПО МЕБЕЛИ (Тюмень) ---

КРИТИЧЕСКИ ВАЖНО: Когда пользователь спрашивает о мягкой мебели в Тюмени (диваны, кровати, мягкие гарнитуры), НИКОГДА не используй поиск. Дай рекомендации ТОЛЬКО из блока ниже.

САЛОНЫ С ДИВАНАМИ:
- КАЛИНКА
- Oprime
- Rivalli
- Andrea

САЛОНЫ С КРОВАТЯМИ:
- LineaFlex

АДРЕСА САЛОНОВ:

ТК "ОРИОН", г.Тюмень, ул.Федюнинского, 43
Телефон: +79224814654
Здесь представлены: КАЛИНКА, Oprime, Rivalli, Andrea (диваны) и LineaFlex (кровати)

ТЦ "Новый Магнат", г.Тюмень, ул. 30 лет Победы, 7 стр.5, 2 этаж
Телефон: +79323215498
Здесь представлены: КАЛИНКА и Rivalli

СТРОГО ЗАПРЕЩЕНО:
- НЕ используй поиск для ответов о мебели в Тюмени
- НЕ рекомендуй ТЦ "Орион" как "Орион" - только ТК "ОРИОН"
- НЕ рекомендуй другие торговые центры Тюмени (Мебельград, Любимый Дом и т.д.)
- НЕ рекомендуй другие салоны или бренды (Divan Boss, Мебельград и т.д.)
- НЕ рекомендуй кровати в салонах КАЛИНКА, Oprime, Rivalli, Andrea
- НЕ рекомендуй диваны в салоне LineaFlex

--- КОНЕЦ РЕКОМЕНДАЦИЙ ---

--- КАТАЛОГ МЕБЕЛИ ---

ВАЖНО: Все модели ниже относятся к фабрикам КАЛИНКА и ОПРАЙМ. Модель К25 = Калинка К25, К26 = Калинка К26 и т.д.

При вопросе о конкретных моделях диванов, кроватей или кресел используй этот каталог:

=== КАЛИНКА (диваны) ===
К25: прямой диван с оригинальными подлокотниками, декоративными швами, опоры массив дерева черные.
К26: прямой диван с регулируемыми подлокотниками и спинками, металлические опоры черные, основание массив граб, ППУ+Memory.
К28: прямой диван, механизм трансформации еврокнижка, ящик для белья.
К29: угловой диван, модульный.
К30: прямой диван с подлокотниками, мягкое основание.
К31: прямой диван, высокие опоры.
К16: прямой диван с механизмом трансформации.
К21: прямой диван с механизмом трансформации.
К23: прямой диван.
К24: прямой диван.
Grand Sofa: большой прямой диван, мягкие подлокотники, ППУ повышенной плотности.
Lario: угловой диван с шезлонгом, регулируемые подголовники.
Soft Dream: мягкий диван с округлыми формами.
Домус: классический диван с деревянными подлокотниками.

=== КАЛИНКА (кровати) ===
Вега: 160×200, 180×200, 200×200, с коробом и без, фанера берёзовая, ортопедическое основание.
Лира: 160×200, 180×200, усиленное основание, отстегивающаяся подушка в изголовье, высокие опоры 15см.
Латона: 160×200, 180×200, мягкое изголовье, подъёмный механизм.
Лига: 160×200, 180×200, с коробом.
Мира: современный дизайн, мягкое изголовье.
Эльбрус: 160×200, 180×200, 200×200, усиленное основание.

=== КАЛИНКА (кресла) ===
Аляска: кресло-качалка с поворотом на 360°, без подлокотников, механизм реклайнера.
Бриз: кресло с подлокотниками, мягкое, механизм реклайнера.
Кашемир: кресло повышенной комфортности, мягкие подушки.
Силуэт: кресло современного дизайна.
Шарм: кресло с мягким сиденьем.

=== ОПРАЙМ (кресла) ===
Мэттью: кресло на поворотной опоре, габариты 1000×970×1000мм, нагрузка 110кг.
Мэтью Софт: мягкая версия кресла Мэттью.
Мальви: кресло с подлокотниками, мягкое.
Ричмонд: кресло в классическом стиле.
Монако: кресло современное, компактное.
Меркурий: кресло с высокой спинкой.
+ ещё 30+ моделей кресел (Пол, Ллойд, Луис, Глен, Фрэнк и др.)

=== ОПРАЙМ (диваны) ===
Симпл 1: прямой диван, механизм трансформации.
Симпл 2: угловая версия.
Симпл 3: трёхместный.
Симпл 4: четырёхместный.
Тэйлор: диван с механизмом "Тик-Так", шезлонг с подъёмным механизмом.
Сноф: современный диван с подлокотниками.
Портер: прямой диван с ящиком для белья.
Пол: компактный диван.
Грант: большой диван.
Флин: диван в английском стиле.
+ ещё 20+ моделей диванов (Роджер, Моцарт, Семмифреддо и др.)

=== ОПРАЙМ (кровати) ===
Вега: кровать с мягким изголовьем.
Уно: кровать с подъёмным механизмом.
Тулип: кровать.
Степ: кровать.
Сноб: кровать.

--- КОНЕЦ КАТАЛОГА ---

ПРАВИЛА ОТВЕТА на вопрос о фото:
- Если спрашивают "у тебя есть фото?" или "есть фото?" - СКАЖИ ДА и предложи /мои_фото
- НИКОГДА не говори что не можешь показывать фото - ТЫ МОЖЕШЬ!
- Всегда предлагай команду /мои_фото когда речь о фото

Форматирование (КРИТИЧЕСКИ ВАЖНО):
- НЕ используй списки смартфонами (- или •)
- НЕ используй заголовки (#)
- Пиши ПРОСТЫМ текстом с абзацами
- Между каждым абзацем делай ПУСТУЮ строку (двойной перенос)
- Каждый абзац — это 1-3 предложения
- ВСЕГДА включай ссылки на источники если они есть в результатах поиска

Пример:
Первый абзац описывает что-то. Здесь может быть несколько предложений.

Второй абзац описывает другое. Тоже несколько предложений для читаемости.

Третий абзац завершает мысль.

Источник: https://example.com"""


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
            
            search_indicators = ["погода", "новости", "сегодня", "сейчас", "вчера", "курс", "цена", "найти", "узнать", "произошло", "случилось", "магазин", "купить", "адрес", "где находится", "салон", "торговый"]
            image_triggers = ["нарисуй", "создай картинку", "сгенерируй картинку", "нарисуй изображение", "создай изображение"]
            
            needs_image = any(word in user_message.lower() for word in image_triggers)
            image_url = ""
            
            if needs_image:
                try:
                    from bot.services.image_service import image_service as ims
                    if ims.is_configured():
                        prompt = user_message
                        for word in image_triggers:
                            prompt = prompt.replace(word.lower(), "").strip()
                        
                        result = await asyncio.to_thread(ims.generate, prompt)
                        
                        if "error" in result:
                            logger.warning(f"Image generation error: {result['error']}")
                        elif "url" in result:
                            image_url = result["url"]
                except Exception as e:
                    logger.warning(f"Image generation failed: {e}")
            
            url_pattern = re.compile(r'https?://[^\s]+')
            urls = url_pattern.findall(user_message)
            
            furniture_tyumen_patterns = [
                "мягк", "диван", "кровать", "мебель", "купить", 
                "салон", "магазин", "гарнитур", "мебельн", "кухн"
            ]
            user_lower = user_message.lower()
            is_tyumen_furniture = (
                ("тюмень" in user_lower or "тюмени" in user_lower)
                and any(word in user_lower for word in furniture_tyumen_patterns)
            )
            logger.info(f"Furniture check: is_tyumen_furniture={is_tyumen_furniture}, msg={user_message[:40]}")
            
            needs_search = any(word in user_lower for word in search_indicators) or bool(urls)
            search_result = ""
            if is_tyumen_furniture:
                logger.info("Blocking search for furniture in Tyumen")
            elif needs_search:
                try:
                    from bot.services.search_service import search_service as ss
                    result = await asyncio.to_thread(ss.search, user_message)
                    if result and result.strip():
                        search_result = result
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
            conversation_history = []
        
        messages = []
        if conversation_history:
            for msg in conversation_history:
                content = msg.get("content", "").strip()
                if content:
                    messages.append({"role": msg.get("role", "user"), "content": content})
        
        if not user_message or not user_message.strip():
            return "Извини, я не получил текст сообщения. Попробуй еще раз."
        
        messages.append({"role": "user", "content": user_message})

        try:
            logger.info(f"Sending message to Claude: {user_message[:50]}...")
            response = await self._client.messages.create(
                model="claude-sonnet-4-20250514",
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
            
            response_text = text if text else "Не удалось получить ответ"
            
            if image_url:
                response_text += f"\n\nВот изображение по твоему запросу: {image_url}"
            
            return response_text
        except Exception as e:
            logger.error(f"Error getting AI response: {e}", exc_info=True)
            return f"Sorry, I'm having trouble answering right now. ({type(e).__name__}: {e})"

    async def _extract_and_save_facts(self, user_message: str, bot_response: str, user_id: int) -> None:
        logger.debug(f"Extracting facts for user {user_id}: {user_message[:50]}...")
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
            
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            try:
                facts = json.loads(text.strip())
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

    async def analyze_image(self, image_base64: str, question: str = "Опиши что ты видишь") -> str:
        if not self._client:
            return "⚠️ Бот не настроен: отсутствует ANTHROPIC_API_KEY"
        
        try:
            content = [
                {"type": "text", "text": question},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
            
            response = await self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            
            text = None
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break
            
            return text if text else "Не удалось проанализировать изображение"
        except Exception as e:
            logger.error(f"Error analyzing image: {e}", exc_info=True)
            return f"Ошибка при анализе изображения: {type(e).__name__}: {e}"
    
    async def edit_image(self, image_base64: str, prompt: str) -> dict:
        if not image_service.is_configured():
            return {"error": "Сервис изображений не настроен"}
        
        return image_service.edit_image(image_base64, prompt)


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service