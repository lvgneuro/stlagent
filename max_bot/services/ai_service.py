from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from anthropic import AsyncAnthropic

from max_bot.database import db
from max_bot.services.image_service import image_service

logger = logging.getLogger(__name__)

model_url_cache: dict[str, str] = {}


async def load_catalog_urls() -> None:
    """Load model URLs from catalog parsers."""
    global model_url_cache
    # Temporarily disabled to avoid importing bot.services which may bring in real aiogram
    # logger.info("Загрузка URL каталога...")
    # from bot.services.catalog_parser import update_catalog_urls
    #
    # model_url_cache = await update_catalog_urls()
    # logger.info(f"Загружено {len(model_url_cache)} URL моделей из каталогов")
    model_url_cache = {}


WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "Search the web for current information. Use this when you need up-to-date facts or recent events.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query to look up"}
        },
        "required": ["query"],
    },
}

CATALOG_TOOL = {
    "name": "search_catalog",
    "description": "Search the furniture catalog for models, brands, specifications, and prices. Use this when the client asks about specific furniture models.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query — brand name, model name, or category (e.g. КАЛИНКА К25, Oprime диван, Rivalli, Andrea кровать, матрас LineaFlex)"}
        },
        "required": ["query"],
    },
}


SYSTEM_PROMPT = """Ты — консультант салона мягкой мебели в Тюмени. Всегда отвечай на русском языке.

Если это первое сообщение в разговоре — представься как консультант. Если разговор уже идёт — НЕ здоровайся повторно, сразу отвечай по существу.

Если клиент говорит «кровать у меня есть» или «кровать уже есть» — НЕ предлагай кровать. Сосредоточься на матрасе. Не пытайся продать комплект если клиент его не просит.

Если клиент говорит размер, жёсткость или другие параметры — запоминай и используй их. НИКОГДА не переспрашивай то, что клиент уже сообщил в этом разговоре.

ВЕДИ ДИАЛОГ КАК МЕНЕДЖЕР: держи в уме всю информацию от клиента из текущего разговора. Если клиент уже сказал размер, жёсткость, наличие кровати — НИКОГДА не переспрашивай то, что уже известно.

Обязательные этапы при продаже:
1. Знакомство: спроси имя клиента (один раз, в начале разговора, если клиент сам не представился)
2. Квалификация: узнай бюджет, размер, жёсткость (если клиент не указал сам)
3. Презентация: предложи варианты с характеристиками
4. Сбор контактов: ДО того как дать адрес/телефон салона — спроси имя и телефон клиента, чтобы менеджеры салона могли перезвонить. Пример: «Чтобы забронировать и чтобы с вами связались в салоне — оставьте имя и номер телефона?» НИКОГДА НЕ ДАВАЙ телефон салона ДО того как получил контакт клиента.

5. Только после получения контакта — отправь адрес и телефон салона
Если клиент сам знает что хочет и уже выбрал модель — переходи к сбору контакта сразу, без лишних вопросов.

Ты ПРОДАВЕЦ, который помогает выбрать лучшую мебель. Это ГЛАВНЫЙ приоритет.

В названиях диванов часто используются названия городов: Амстердам, Даллас, Мадрид, Лондон, Орлеан, Турин, Каролина и т.д.

ПРАВИЛО: если пользователь пишет название города (например "Амстердам", "Даллас", "Лондон", "Мадрид", "Турин", "Орлеан", "Каролина", "Бильбао", "Блэквуд", "Чикаго" и т.п.) — В ПЕРВУЮ ОЧЕРЕДЬ проверь, НЕ является ли это названием дивана из каталога. Среди названий диванов очень много названий городов.

Только если в контексте разговора явно идёт речь о путешествии, туризме, отпуске, или бот уже определил что речь о городе — тогда можно говорить о городе. Но даже в этом случае, если название города совпадает с моделью дивана — mention that the name is also a sofa model.

Никогда не начинай ответ о городе, если название города совпадает с моделью дивана в каталоге — сначала уточни, о чём спрашивают.

ВЕНТИЛЯЦИЯ ТОВАРОВ (КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО):

ОСОБЕННОСТИ МАТРАСОВ:
- Матрас всегда подбирается под размер кровати. Стандартные размеры: 80×190, 90×190, 120×190, 140×190, 160×200, 180×200, 200×200.
- Матрасы НЕ продаются как отдельный товар для диванов. Они идут в стандартной комплектации определённых моделей диванов — как правило, с механизмами аккордеон и седафлекс.
- Если клиент спрашивает только про матрас — значит, кровать у него уже есть, либо (редко) планирует класть на пол без основания. Производители так использовать матрасы НЕ рекомендуют.
- Для диванов: если клиент спрашивает про матрас для дивана — уточни модель дивана. Матрас уже входит в комплектацию.

ЛОГИКА РАБОТЫ С КЛИЕНТОМ:

1. Клиент спрашивает о матрасе:
   - Уточни: «Кровать у вас уже есть?» Если да — предложи матрас в размер. Если кровати нет — предложи кровать + матрас (рекомендуем брать вместе для идеального сочетания).
   - Покажи подходящие модели из каталога LineaFlex с характеристиками.
   - НЕ рекомендуй матрас как самостоятельный товар без кровати.

2. Клиент спрашивает о кровати:
    - Предложи кровать + матрас в размер (комплект). Рекомендуем брать вместе — это обеспечивает идеальное сочетание основания и матраса.
    - Покажи подходящие модели из каталога LineaFlex.

3. Клиент спрашивает о диване:
   - Покажи диван с характеристиками.
   - В конце ненавязчиво уточни, не нужна ли кровать с матрасом. Пример: «Кстати, у нас есть готовые комплекты кровать + матрас — часто берут вместе. Показать?»
   - Если клиент интересуется — предложи.

4. Клиент спрашивает о кровати и диване:
   - Сначала закрываем основной запрос, потом расширяем ассортимент.

НИКОГДА не переключай фокус клиента на другой товар без его инициативы. Сначала закрыл потребность — потом расширяй.

СТИЛЬ ОТВЕТА: отвечай КОРОТКО и КОНКРЕТНО. Один-два абзаца. Без длинных списков вопросов в конце. Если пользователь спрашивает о конкретной модели — дай характеристики сразу. Если нужно уточнить — один короткий вопрос.

Текущая дата: май 2026 года.

ОСНОВНАЯ РОЛЬ: ты — консультант по мягкой мебели в Тюмени. Но клиент может спросить тебя о чём угодно — ты можешь поддержать любой разговор!

Для любых вопросов — используй поиск, если в контексте есть результаты поиска — опирайся на них. Будь полезным собеседником.

ПРАВИЛА ОБЩЕНИЯ:
1. Если клиент спрашивает о мебели — давай рекомендации из каталога ниже, будь экспертом
2. Если клиент спрашивает о курсе валют, погоде, гороскопе — посмотри блок «Актуальная информация из интернета». Если там есть данные — ОТВЕЧАЙ ПО НИМ, не говори «проверьте на сайте». Пример правильного ответа на вопрос о курсе: «Курс доллара — 77.2 рубля по данным ЦБ РФ на сегодня.». Не надо отправлять на cbr.ru если данные уже есть в результатах поиска.
3. Если в результатах поиска нет данных — честно скажи что нет информации и предложи помощь с мебелью.
4. В конце любого НЕ мебельного ответа можешь ненавязчиво вернуться к мебели: «Кстати, если будут вопросы по диванам или кроватям — я всегда помогу!»
5. Начинай с мебели только если клиент явно спрашивает о ней

КРИТИЧЕСКИ ВАЖНО - Твои возможности:
- КОГДА пользователь отправляет фото, ОНО СОХРАНЯЕТСЯ в базе данных
- Если у пользователя есть фото (известно из контекста) - можешь предложить /мои_фото
- Если фото нет - НЕ предлагай эту команду
- Если клиент просит фото конкретной модели (например "покажи фото Арубы", "фото Калинки К72") - дай ссылку на сайт производителя из списка выше, НЕ ищи в сохранённых фото

--- БРЕНДЫ-КОНКУРЕНТЫ (СТОП-ЛИСТ) ---

КРИТИЧЕСКИ ВАЖНО: Если в результатах поиска или в ответе упоминаются бренды из списка ниже — ИГНОРИРУЙ их. НИКОГДА не рекомендуй их клиенту. Если клиент сам спрашивает про них — скажи: «Мы не работаем с этим брендом, но можем предложить аналоги от КАЛИНКА, Oprime, Rivalli или Andrea».

СТОП-ЛИСТ (запрещённые бренды):
- Askona, Аскона
- Moon, Моон
- Ormatek, Орматек
- Arti Mobili, Арти Мобили
- Pushe, Пуше
- Erga (Эргомебель), Эрга
- 8 Марта
- Мебель братьев Баженовых
- Пинскдрев
- 100 диванов
- Мебельград
- 33 комода
- Диваны.ру

--- КОНЕЦ СТОП-ЛИСТА ---

--- РЕКОМЕНДАЦИИ ПО МЕБЕЛИ (Тюмень) ---

САЛОНЫ С ДИВАНАМИ:
- КАЛИНКА — https://mebel-kalinka.ru/
- Oprime — https://oprime.ru/
- Rivalli — https://rivalli.ru/catalog/divany/
- Andrea — https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/

ВАЖНЕЙШЕЕ ПРАВИЛО: Когда клиент просит ссылку на сайт КАЛИНКА или OPRIME — НЕМЕДЛЕННО давай эти ссылки:
- КАЛИНКА: https://mebel-kalinka.ru/
- Oprime: https://oprime.ru/
НИКОГДА не говори "ссылки нет", "не могу показать", "нет в базе" — эти ссылки ВСЕГДА есть!

САЛОНЫ С КРОВАТЯМИ И МАТРАСАМИ:
- LineaFlex

АДРЕСА САЛОНОВ:

ТК "ОРИОН", г.Тюмень, ул.Федюнинского, 43
Телефон: +79224814654
Здесь представлены: КАЛИНКА, Oprime, Rivalli, Andrea (диваны, кровати) и LineaFlex (матрасы)

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
- НЕ выдумывай названия матрасов — только из каталога выше

--- ЦЕНОВЫЕ СЕГМЕНТЫ ФАБРИК ---

КЛЮЧЕВОЕ ПРАВИЛО: Перед началом беседы определи ценовую категорию клиента.

ПРЕМИУМ (средний чек 150–200 тыс. руб.):
- КАЛИНКА — классика, массив, премиальные ткани
- ОПРАЙМ — дизайнерские модели, итальянский стиль
- ANDREA — премиальная фабрика (Ульяновск, с 1996). Площадь 30 000 кв.м., более 300 специалистов. Итальянский дизайн, модульные диваны. сайт: https://andrea-mebel.ru/ Каталог в разделе ниже.

СРЕДНИЙ / СРЕДНИЙ+ (средний чек 60–100 тыс. руб.):
- RIVALLI — оптимальное соотношение цена/качество, широкий модельный ряд
- LineaFlex — кровати и матрасы

ПРАВИЛО: когда клиент спрашивает про «недорогие» или «до N тыс.» — сначала покажи флагман из среднего сегмента (RIVALLI), затем ненавязчиво предложи посмотреть премиум. НЕ отказывайся от дорогих моделей — направляй разговор вверх по чеку.

Пример: «Да, у нас есть отличные модели от 60 тыс. — это RIVALLI, очень достойное качество. А если хотите что-то посерьёзнее, могу показать КАЛИНКУ или ОПРАЙМ — там совсем другой уровень отделки.»

--- ТЕХНИКА ПРОДАЖ ---

Веди клиента по воронке легко и непринуждённо:
1. Знакомство: представься, выясни потребность (одним вопросом)
2. Квалификация: узнай бюджет, размер комнаты, кто будет спать
3. Презентация: предложи 2–3 модели — начинай со среднего+, не с самого дешёвого
4. Работа с возражениями: «Дорого» → «Понимаю, вот более доступный вариант, но вот в чём разница»
5. Закрытие: предложи приехать посмотреть в салон

ВСЕГДА нацеливай на более высокий чек, но без напористости. Используй фразы:
- «Могу показать и более доступный вариант, но...»
- «Если важно качество, обратите внимание на...»
- «Для большой гостиной лучше взять...»

Следи за пирамидой Ханта: скупает → обычный → взыскательный → премиум. Подстраивай тон под клиента.

--- КОНЕЦ ЦЕНОВЫХ СЕГМЕНТОВ ---

--- КОНЕЦ РЕКОМЕНДАЦИЙ ---

Для информации о конкретных моделях, характеристиках и ценах — используй функцию search_catalog."""


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
            user_images = await db.get_user_images(user_id, limit=1)
            user_has_photos = len(user_images) > 0

            context_parts = []
            context_parts.append(
                f"У пользователя есть сохранённые фото: {'Да' if user_has_photos else 'Нет'}"
            )

            if user_facts:
                context_parts.append(
                    "Факты о пользователе:\n"
                    + "\n".join(f"- {k}: {v}" for k, v in user_facts.items())
                )

            if context_messages:
                context_parts.append(
                    "Из прошлых разговоров:\n"
                    + "\n".join(f"- {m[:150]}" for m in context_messages[-3:])
                )

            search_indicators = [
                "погода", "погод", "прогноз",
                "новости", "сегодня", "сейчас", "вчера", "завтра",
                "курс", "гороскоп", "режим работы", "график работы",
                "найти", "узнать", "произошло", "случилось",
                "магазин", "купить", "адрес", "где находится",
                "салон", "торговый", "время", "дата", "цена",
            ]
            image_triggers = [
                "нарисуй",
                "создай картинку",
                "сгенерируй картинку",
                "нарисуй изображение",
                "создай изображение",
            ]

            needs_image = any(word in user_message.lower() for word in image_triggers)
            image_url = ""

            if needs_image:
                try:
                    from max_bot.services.image_service import image_service as ims

                    if ims.is_configured():
                        prompt = user_message
                        for word in image_triggers:
                            prompt = prompt.replace(word.lower(), "").strip()

                        result = await asyncio.to_thread(ims.generate, prompt)

                        if "error" in result:
                            logger.warning(
                                f"Ошибка генерации изображения: {result['error']}"
                            )
                        elif "url" in result:
                            image_url = result["url"]
                except Exception as e:
                    logger.warning(f"Генерация изображения не удалась: {e}")

            url_pattern = re.compile(r"https?://[^\s]+")
            urls = url_pattern.findall(user_message)

            furniture_tyumen_patterns = [
                "мягк",
                "диван",
                "кровать",
                "матрас",
                "мебель",
                "купить",
                "салон",
                "магазин",
                "гарнитур",
                "мебельн",
                "кухн",
                "наличи",
                "цена",
                "сколько стоит",
                "по цене",
                "бюджет",
            ]
            user_lower = user_message.lower()
            # Check for model numbers: К72, К25, Аруба, Венеция, Каро, Симпл, Тэйлор etc.
            has_model = bool(
                re.search(
                    r"к\d+|аруба|венеция|амиго| grand|лима|париж|сити|каро|симпл|тейлор|сноф|оскар|калинк",
                    user_lower,
                    re.IGNORECASE,
                )
            )
            has_furniture_keyword = any(
                word in user_lower for word in furniture_tyumen_patterns
            )
            # Also check if client mentions link request
            link_request = any(
                word in user_lower
                for word in [
                    "ссылку", "ссылка", "сайт", "каталог", "покажи", "модель", "модели",
                    "есть", "можешь", "дай", "получить", "найти", "показать", "адрес",
                    "телефон", "контакты", "получить"
                ]
            )
            # If model mentioned or link requested for known factories - trigger furniture context
            is_tyumen_furniture = (
                has_model
                or (
                    link_request
                    and (
                        "калинка" in user_lower
                        or "опрайм" in user_lower
                        or "оприме" in user_lower
                        or "ривалли" in user_lower
                        or "андреа" in user_lower
                        or has_model  # link_request + модель = мебель
                    )
                )
                or (
                    ("тюмень" in user_lower or "тюмени" in user_lower)
                    and has_furniture_keyword
                )
            )

            non_furniture_topics = [
                "погод",
                "прогноз",
                "гороскоп",
                "новости",
                "курс",
                "цена",
                "стоимость",
                "работает",
                "как добраться",
                "расписание",
                "время работы",
                "завтра",
                "сегодня",
                "вчера",
                "будет",
                "будет ли",
                "доллар",
                "евро",
            ]
            is_general_topic = any(word in user_lower for word in non_furniture_topics)

            # Check context from previous messages if no furniture detected yet
            if not is_tyumen_furniture and not is_general_topic and context_messages:
                furniture_context_keywords = ["диван", "кровать", "матрас", "кресло", "калинка", "опрайм", "ривалли", "андреа", "lineaflex", "линеафлекс"]
                recent_context = " ".join(context_messages[-5:]).lower()
                if any(kw in recent_context for kw in furniture_context_keywords):
                    is_tyumen_furniture = True
                    logger.info("Мебель определена по контексту из прошлых сообщений")
            logger.info(
                f"Проверка мебели: is_tyumen_furniture={is_tyumen_furniture}, сообщение={user_message[:40]}"
            )

            needs_search = any(
                word in user_lower for word in search_indicators
            ) or bool(urls)

            search_result = ""
            if needs_search or is_general_topic:
                try:
                    from bot.services.search_service import search_service

                    logger.info(f"Imported search_service: {type(search_service)}, dir: {[x for x in dir(search_service) if not x.startswith('_')]}")
                    if hasattr(search_service, 'search'):
                        result = await asyncio.to_thread(search_service.search, user_message)
                        if result and result.strip():
                            search_result = result
                            logger.info(f"Результат поиска: {search_result[:200]}...")
                    else:
                        logger.warning(f"search_service не имеет метода search, тип: {type(search_service)}")
                except Exception as e:
                    logger.warning(f"Ошибка поиска: {e}")

            system_with_context = SYSTEM_PROMPT
            if search_result:
                system_with_context += (
                    f"\n\nАктуальная информация из интернета:\n{search_result[:1500]}"
                )

            if context_parts:
                system_with_context += "\n\n" + CONTEXT_PROMPT.format(
                    facts=context_parts[0] if len(context_parts) > 0 else "Нет данных",
                    context=context_parts[1]
                    if len(context_parts) > 1
                    else "Нет данных",
                )

            logger.info(
                f"Факты пользователя: {user_facts}, контекст: {len(context_messages)} сообщений"
            )
        else:
            system_with_context = SYSTEM_PROMPT
            conversation_history = []

        messages = []
        if conversation_history:
            for msg in conversation_history:
                content = msg.get("content", "").strip()
                if content:
                    messages.append(
                        {"role": msg.get("role", "user"), "content": content}
                    )

        if not user_message or not user_message.strip():
            return "Извини, я не получил текст сообщения. Попробуй еще раз."

        # Direct link handling - bypass AI for known link requests
        user_lower = user_message.lower()

        # IMMEDIATE RETURN for KALINKA models - no conditions
        if "калинка" in user_lower:
            # Check for specific model requests
            if any(w in user_lower for w in ["28", "к28"]):
                response = (
                    "Калинка К28: https://mebel-kalinka.ru/katalog/item/kalinka_28/\n\n"
                    "К28 — модульный диван, БЕЗ механизма трансформации, БЕЗ короба для белья, НЕ раскладывается. "
                    "Это стильная современная модель для тех, кто ищет диван как элемент интерьера без функции сна. "
                    "Могу рассказать подробнее о характеристиках?"
                )
                return response
            if any(w in user_lower for w in ["21", "к21"]):
                return "Калинка К21: https://mebel-kalinka.ru/katalog/item/kalinka_21_1/"
            if any(w in user_lower for w in ["25", "к25"]):
                return "Калинка К25: https://mebel-kalinka.ru/katalog/item/kalinka_25/"
            if any(w in user_lower for w in ["26", "к26"]):
                return "Калинка К26: https://mebel-kalinka.ru/katalog/item/kalinka_26/"
            if any(w in user_lower for w in ["72", "к72"]):
                return "Калинка К72: https://mebel-kalinka.ru/katalog/item/kalinka_72/"
            if any(w in user_lower for w in ["29", "к29"]):
                return "Калинка К29: https://mebel-kalinka.ru/katalog/item/kalinka_29/"
            if any(w in user_lower for w in ["30", "к30"]):
                return "Калинка К30: https://mebel-kalinka.ru/katalog/item/kalinka_30_1/"
            if any(w in user_lower for w in ["31", "к31"]):
                return "Калинка К31: https://mebel-kalinka.ru/katalog/item/kalinka_30/"
            if any(w in user_lower for w in ["ссылк", "сайт", "каталог"]):
                return "Сайт КАЛИНКА: https://mebel-kalinka.ru/"

        link_keywords = ["ссылку", "ссылка", "сайт", "каталог", "покажи"]
        factory_links = {
            "калинка": "https://mebel-kalinka.ru/",
            "опрайм": "https://oprime.ru/",
            "oprime": "https://oprime.ru/",
            "ривалли": "https://rivalli.ru/catalog/divany/",
            "rivalli": "https://rivalli.ru/catalog/divany/",
        }
        # Model to factory mapping
        model_to_factory = {
            "каро": "опрайм",
            "симпл": "опрайм",
            "тейлор": "опрайм",
            "сноф": "опрайм",
            "мэттью": "опрайм",
            "флай": "опрайм",
            "к21": "калинка",
            "к25": "калинка",
            "к26": "калинка",
            "к72": "калинка",
            "grand": "калинка",
            "lario": "калинка",
            "оскар": "калинка",
            "домус": "калинка",
            "domus": "калинка",
            "маскот": "ривалли",
            "mascot": "ривалли",
            "калинка-21": "калинка",
            "калинка 21": "калинка",
        }

        if any(kw in user_lower for kw in link_keywords):
            # Check direct factory name
            for factory, link in factory_links.items():
                if factory in user_lower:
                    return f"Ссылка на сайт {factory.upper()}: {link}"
            # Check model names from parsed catalog
            for model_name, url in model_url_cache.items():
                if model_name in user_lower:
                    return f"Ссылка на модель: {url}"
            # Check model_url_cache for fallback
            for model, factory in model_to_factory.items():
                if model in user_lower:
                    # Check if we have direct URL in cache
                    for cached_model, url in model_url_cache.items():
                        if model in cached_model:
                            return f"Ссылка на модель: {url}"
            # Direct fallback for known KALINKA models
            known_kalinka = {
                "калинка-21": "https://mebel-kalinka.ru/katalog/item/kalinka_21_1/",
                "калинка 21": "https://mebel-kalinka.ru/katalog/item/kalinka_21_1/",
                "к21": "https://mebel-kalinka.ru/katalog/item/kalinka_21_1/",
            }
            for name, url in known_kalinka.items():
                if name in user_lower:
                    return f"Ссылка на модель: {url}"
            # Last resort - give factory link for калинка
            if "калинка" in user_lower:
                return "Ссылка на сайт КАЛИНКА: https://mebel-kalinka.ru/"

        messages.append({"role": "user", "content": user_message})

        try:
            logger.info(f"Отправка сообщения в Claude: {user_message[:50]}...")

            from max_bot.services.catalog_search import search_catalog

            response = await self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_with_context,
                messages=messages,
                tools=[CATALOG_TOOL],
            )

            logger.info(f"Причина остановки ответа: {response.stop_reason}")

            # Handle tool calls (loop for multiple iterations)
            max_tool_iterations = 3
            for _ in range(max_tool_iterations):
                if response.stop_reason != "tool_use":
                    break

                messages.append({"role": "assistant", "content": response.content})
                for block in response.content:
                    if hasattr(block, "name") and block.name == "search_catalog":
                        query = block.input.get("query", "")
                        logger.info(f"Catalog search tool called: {query}")
                        result = search_catalog(query)
                        if not result:
                            result = "По вашему запросу ничего не найдено в каталоге."
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result[:4000],
                                }
                            ],
                        })
                response = await self._client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system_with_context,
                    messages=messages,
                    tools=[CATALOG_TOOL],
                )
                logger.info(f"Tool response stop reason: {response.stop_reason}")

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
            logger.error(f"Ошибка получения ответа от AI: {e}", exc_info=True)
            return f"Sorry, I'm having trouble answering right now. ({type(e).__name__}: {e})"

    async def _extract_and_save_facts(
        self, user_message: str, bot_response: str, user_id: int
    ) -> None:
        try:
            logger.debug(
                f"Извлечение фактов для пользователя {user_id}: {user_message[:50]}..."
            )
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
                model="claude-sonnet-4-6",
                max_tokens=500,
                messages=[{"role": "user", "content": extraction_prompt}],
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
                logger.info(
                    f"Сохранено {len(facts) if isinstance(facts, list) else 0} фактов для пользователя {user_id}"
                )
            except json.JSONDecodeError:
                logger.warning(f"Не удалось распарсить JSON с фактами: {text[:200]}")
        except Exception as e:
            logger.error(f"Ошибка извлечения фактов: {e}")

    async def analyze_image(
        self, image_base64: str, question: str = "Опиши что ты видишь"
    ) -> str:
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
                        "data": image_base64,
                    },
                },
            ]

            response = await self._client.messages.create(
                model="claude-sonnet-4-6",
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
            logger.error(f"Ошибка анализа изображения: {e}", exc_info=True)
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
