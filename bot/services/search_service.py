from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

from tavily import TavilyClient
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class SearchService:

    STOP_LIST = [
        "askona", "аскона",
        "moon", "моон",
        "ormatek", "орматек",
        "arti mobili", "арти мобили",
        "pushe", "пуше",
        "erga", "эрга", "эргомебель",
        "8 марта",
        "братьев баженовых",
        "пинскдрев",
        "100 диванов",
        "мебельград",
        "33 комода",
        "диваны.ру", "диваны ру",
    ]

    def __init__(self) -> None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY not found in .env file")
        self._tavily = TavilyClient(api_key=tavily_key)
        self._ddgs = DDGS()

    def _search_web(self, query: str) -> str:
        """Try Tavily first, fall back to DuckDuckGo HTML backend."""
        result = self._search_tavily(query)
        if result:
            return result
        result = self._search_duckduckgo(query)
        return result if result else ""

    def _search_duckduckgo(self, query: str) -> str:
        try:
            results = list(self._ddgs.text(query, max_results=8, backend="html"))
            if not results:
                return ""
            summary = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                if not title or not body:
                    continue
                summary.append(f"- {title}: {body[:300]}")
            return "\n\n".join(summary) if summary else ""
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return ""

    def _search_tavily(self, query: str) -> str:
        try:
            results = self._tavily.search(
                query=query,
                max_results=5,
                include_answer=True,
            )
            if results.get("answer"):
                summary = [f"Краткий ответ: {results['answer'][:500]}"]
            else:
                summary = []
            if results.get("results"):
                for r in results["results"][:3]:
                    content = r.get("content", "")[:200]
                    title = r.get("title", "")
                    if title and content:
                        summary.append(f"- {title}: {content}")
            return "\n\n".join(summary) if summary else ""
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")
            return ""

    @staticmethod
    def _clean_query(raw: str) -> str:
        stop_words = {
            "дашь", "дай", "дайте", "знаешь", "знаете", "расскажи", "расскажите",
            "пожалуйста", "наконец", "есть", "можешь", "можете", "хочешь",
            "скажи", "найди", "покажи", "покажите", "ищу", "ищете",
            "нужен", "нужна", "нужно", "нужны", "подскажи", "может",
            "где", "когда", "как", "что", "зачем", "почему",
            "тебя", "меня", "мне", "тебе", "себя", "себе",
            "там", "тут", "здесь", "сейчас", "сегодня", "вчера", "завтра",
            "так", "сделать", "сделал", "сделали", "сделай", "сделаю",
            "делать", "делаю", "делаешь", "делаем", "делаете",
            "просто", "вообще", "ладно", "хорошо", "конечно",
            "ну", "ой", "ах", "эх", "вот", "это", "этот",
            "деплой", "деплоя", "деплою",
            "на", "от", "до", "про", "для", "без", "через",
            "мой", "моя", "моё", "мои", "моего", "моей", "моему",
            "твой", "твоя", "твоё", "твои",
            "ваш", "ваша", "ваше", "ваши",
            "же", "ж", "ли", "бы", "ведь", "даже", "уже",
        }
        import re
        words = re.findall(r"[а-яёa-z]+", raw.lower())
        kept = [w for w in words if w not in stop_words and len(w) > 1]
        return " ".join(kept) if kept else raw

    def _dedup_clean(self, clean: str, word: str) -> str:
        return " ".join(w for w in clean.split() if word not in w)

    def _weather_api(self, city: str = "Тюмень") -> str:
        try:
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=ru"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            current = data.get("current_condition", [{}])[0]
            temp = current.get("temp_C", "?")
            desc = current.get("lang_ru", [{}])[0].get("value", "")
            feels = current.get("FeelsLikeC", "?")
            wind = current.get("windspeedKmph", "?")
            humid = current.get("humidity", "?")
            lines = [
                f"Погода в {city} сейчас: {desc}",
                f"Температура: {temp}°C (ощущается как {feels}°C)",
                f"Ветер: {wind} км/ч, влажность: {humid}%",
            ]
            forecast = data.get("weather", [])
            if len(forecast) > 1:
                for day in forecast[1:]:
                    date = day.get("date", "")
                    temp_max = day.get("maxtempC", "?")
                    temp_min = day.get("mintempC", "?")
                    desc_day = day.get("hourly", [{}])[0].get("lang_ru", [{}])[0].get("value", "")
                    lines.append(f"\n{date}: {desc_day}, {temp_min}..{temp_max}°C")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Weather API failed: {e}")
            return ""

    def _currency_api(self) -> str:
        try:
            url = "https://www.cbr-xml-daily.ru/daily_json.js"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            valutes = data.get("Valute", {})
            usd = valutes.get("USD", {})
            eur = valutes.get("EUR", {})
            lines = ["Курсы валют ЦБ РФ на сегодня:"]
            if usd:
                lines.append(f"🇺🇸 Доллар США: {usd.get('Value', '?')} руб.")
            if eur:
                lines.append(f"🇪🇺 Евро: {eur.get('Value', '?')} руб.")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Currency API failed: {e}")
            return ""

    def _horoscope_api(self, sign: str = "") -> str:
        try:
            sign_map = {
                "овен": 1, "телец": 2, "близнецы": 3, "рак": 4,
                "лев": 5, "дева": 6, "весы": 7, "скорпион": 8,
                "стрелец": 9, "козерог": 10, "водолей": 11, "рыбы": 12,
            }
            for name, num in sign_map.items():
                if name in sign.lower():
                    url = f"https://ignio.com/r/dly/export/astrologic/xml/{num}.xml"
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        raw = resp.read().decode("1251")
                    import re
                    m = re.search(r"<today[^>]*>(.*?)</today>", raw, re.DOTALL)
                    if m:
                        text = m.group(1).strip()
                        text = re.sub(r"<[^>]+>", "", text)
                        return f"Гороскоп для {name.capitalize()} на сегодня:\n{text[:500]}"
            return f"Гороскоп на сегодня: {sign} — уточните знак зодиака (овен, телец и т.д.)"
        except Exception as e:
            logger.warning(f"Horoscope API failed: {e}")
            return ""

    def search(self, query: str) -> str:
        try:
            clean = self._clean_query(query)
            lower = query.lower()

            if "погод" in lower:
                result = self._weather_api("Тюмень")
                if result:
                    logger.info(f"Weather API: found for '{query}'")
                    return self._filter_stoplist(result)
                clean_w = self._dedup_clean(clean, "погод")
                search_q = f"погода {clean_w}" if clean_w else "погода сегодня"
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            if "курс" in lower or "доллар" in lower or "евро" in lower:
                result = self._currency_api()
                if result:
                    logger.info(f"Currency API: found for '{query}'")
                    return self._filter_stoplist(result)
                search_q = f"курс {'доллара' if 'доллар' in lower else 'евро'} цб рф сегодня"
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            if "гороскоп" in lower:
                clean_h = self._dedup_clean(clean, "гороскоп")
                result = self._horoscope_api(clean_h)
                if result:
                    logger.info(f"Horoscope API: found for '{query}'")
                    return self._filter_stoplist(result)
                search_q = f"гороскоп {clean_h} сегодня" if clean_h else "гороскоп сегодня"
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            result = self._filter_stoplist(self._search_web(clean if clean else query))
            return result if result else "No results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()
