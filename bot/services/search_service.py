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

    def _search_with_fallback(self, query: str) -> str:
        result = self._search_duckduckgo(query)
        if result:
            return result

        fallback_queries = [
            f"{query} адрес",
            f"{query} магазин",
            f"{query} салон",
            f"{query} site:2gis.ru",
            f"{query} Тюмень адрес где купить",
            "калинка диваны тюмень",
            "калинка мебель тюмень официальный сайт",
            '"Калинка" диван Тюмень купить',
        ]

        seen = set()
        for q in fallback_queries:
            if q.lower() in seen:
                continue
            seen.add(q.lower())
            result = self._search_duckduckgo(q)
            if result:
                return result

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

    def search(self, query: str) -> str:
        try:
            is_weather = "погод" in query.lower()

            if is_weather:
                logger.info(f"Weather query detected: {query}")
                ddg_result = self._filter_stoplist(self._search_duckduckgo(query))
                logger.info(f"DuckDuckGo raw result length: {len(ddg_result) if ddg_result else 0}")
                if ddg_result:
                    logger.info("Found weather via DuckDuckGo")
                    return ddg_result
                fallback = self._filter_stoplist(self._search_with_fallback(query))
                logger.info(f"Fallback result length: {len(fallback) if fallback else 0}")
                return fallback if fallback else "No results found."

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
                ddg_result = self._filter_stoplist(self._search_with_fallback(query))
                if ddg_result:
                    if tavily_result:
                        return self._filter_stoplist(tavily_result + "\n\nЛокальные данные:\n" + ddg_result)
                    return ddg_result

            return tavily_result if tavily_result else "No results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()
