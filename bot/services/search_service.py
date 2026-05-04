from __future__ import annotations

import logging
import os
from tavily import TavilyClient

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self) -> None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY not found in .env file")
        self._client = TavilyClient(api_key=api_key)

    def search(self, query: str) -> str:
        try:
            results = self._client.search(query=query, max_results=5)
            if not results.get("results"):
                return "No results found."
            summary = []
            for r in results["results"]:
                summary.append(f"- {r['title']}: {r['content'][:200]}...")
            return "\n".join(summary)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()