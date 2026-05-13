from __future__ import annotations

import logging
import os

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

    def search(self, query: str) -> str:
        try:
            clean = self._clean_query(query)
            lower = query.lower()

            if "погод" in lower:
                clean = self._dedup_clean(clean, "погод")
                search_q = f"погода {clean}" if clean else "погода сегодня"
                logger.info(f"Weather query: raw='{query}' -> search='{search_q}'")
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            if "курс" in lower or "доллар" in lower or "евро" in lower:
                search_q = f"курс {'доллара' if 'доллар' in lower else 'евро'} цб рф сегодня"
                logger.info(f"Currency query: raw='{query}' -> search='{search_q}'")
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            if "гороскоп" in lower:
                clean = self._dedup_clean(clean, "гороскоп")
                search_q = f"гороскоп {clean} сегодня" if clean else "гороскоп сегодня"
                logger.info(f"Horoscope query: raw='{query}' -> search='{search_q}'")
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            result = self._filter_stoplist(self._search_web(clean if clean else query))
            return result if result else "No results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()
