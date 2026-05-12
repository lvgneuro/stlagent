from __future__ import annotations

import logging
import os

from tavily import TavilyClient
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self) -> None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY not found in .env file")
        self._tavily = TavilyClient(api_key=tavily_key)
        self._ddgs = DDGS()

    def _search_duckduckgo(self, query: str) -> str:
        try:
            results = list(self._ddgs.text(query, max_results=8))
            if not results:
                return ""
            summary = []
            for r in results:
                title = r.get("title", "")
                href = r.get("href", "")
                if title and href:
                    summary.append(f"- {title}: {href}")
            return "\n".join(summary) if summary else ""
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

    def search(self, query: str) -> str:
        try:
            results = self._tavily.search(query=query, max_results=5)
            if results.get("results"):
                summary = []
                for r in results["results"]:
                    summary.append(f"- {r['title']}: {r['content'][:200]}...")
                tavily_result = "\n".join(summary)
            else:
                tavily_result = ""

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
                ddg_result = self._search_with_fallback(query)
                if ddg_result:
                    if tavily_result:
                        return tavily_result + "\n\nЛокальные данные:\n" + ddg_result
                    return ddg_result

            return tavily_result if tavily_result else "No results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()
