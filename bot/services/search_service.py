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

    def _filter_stoplist(self, text: str) -> str:
        if not text:
            return text
        lines = text.split("\n")
        filtered = []
        for line in lines:
            lower = line.lower()
            if any(brand in lower for brand in self.STOP_LIST):
                continue
            filtered.append(line)
        result = "\n".join(filtered)
        return result if result.strip() else text + "\n\n[Результаты по некоторым запросам скрыты по стоп-листу]"

    def _search_duckduckgo(self, query: str) -> str:
        try:
            results = list(self._ddgs.text(query, max_results=8))
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
        words_to_remove = [
            "дашь", "дай", "дайте", "знаешь", "знаете", "расскажи", "расскажите",
            "пожалуйста", "наконец", "есть", "можешь", "можете", "хочешь",
            "скажи", "найди", "покажи", "покажите", "ищу", "ищете",
            "нужен", "нужна", "нужно", "нужны", "подскажи", "может",
            "где", "когда", "как", "что", "зачем", "почему",
            "тебя", "меня", "мне", "тебе", "себя", "себе",
            "там", "тут", "здесь", "сейчас", "сегодня", "вчера", "завтра",
        ]
        result = raw.lower()
        for w in words_to_remove:
            result = result.replace(w, "")
        result = " ".join(result.split())
        return result if result else raw

    def search(self, query: str) -> str:
        try:
            clean = self._clean_query(query)
            lower = query.lower()

            if "погод" in lower:
                search_q = f"погода {clean}" if clean else "погода сегодня"
                logger.info(f"Weather query: raw='{query}' -> search='{search_q}'")
                ddg_result = self._filter_stoplist(self._search_duckduckgo(search_q))
                if ddg_result:
                    return ddg_result
                return "No results found."

            if "курс" in lower or "доллар" in lower or "евро" in lower:
                search_q = f"курс {'доллара' if 'доллар' in lower else 'евро'} цб рф сегодня"
                logger.info(f"Currency query: raw='{query}' -> search='{search_q}'")
                ddg_result = self._filter_stoplist(self._search_duckduckgo(search_q))
                if ddg_result:
                    return ddg_result

            if "гороскоп" in lower:
                search_q = f"гороскоп {clean} сегодня"
                logger.info(f"Horoscope query: raw='{query}' -> search='{search_q}'")
                ddg_result = self._filter_stoplist(self._search_duckduckgo(search_q))
                if ddg_result:
                    return ddg_result

            tavily_result = self._filter_stoplist(self._search_tavily(query))

            non_furniture_topics = [
                "погода",
                "новости",
                "курс",
                "цена",
                "стоимость",
                "работа",
                "как добраться",
                "расписание",
                "время работы",
            ]
            is_general_topic = any(word in query.lower() for word in non_furniture_topics)

            if is_general_topic or not tavily_result:
                ddg_result = self._filter_stoplist(self._search_duckduckgo(clean))
                if ddg_result:
                    if tavily_result:
                        return self._filter_stoplist(tavily_result + "\n\nЛокальные данные:\n" + ddg_result)
                    return ddg_result

            return tavily_result if tavily_result else "No results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()
