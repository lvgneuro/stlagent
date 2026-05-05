from __future__ import annotations

import logging
import os
import httpx

from tavily import TavilyClient

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self) -> None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY not found in .env file")
        self._tavily = TavilyClient(api_key=tavily_key)
        self._gis_api_key = os.getenv("DGIS_API_KEY")

    def _search_2gis(self, query: str, city: str = "") -> str:
        if not self._gis_api_key:
            return ""
        
        try:
            city_lower = city.lower() if city else ""
            search_city = city if city else "Тюмень"
            
            url = f"https://catalog.api.2gis.com//search"
            params = {
                "q": query,
                "region": search_city,
                "fields": "items.name,items.address,items.point,items.schedule",
                "key": self._gis_api_key,
                "limit": 5
            }
            
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, params=params)
                data = resp.json()
                
                if "result" not in data or not data["result"].get("items"):
                    return ""
                
                items = data["result"]["items"]
                summary = []
                for item in items[:5]:
                    name = item.get("name", "Unknown")
                    addr = item.get("address", "")
                    summary.append(f"- {name}: {addr}")
                
                return "\n".join(summary) if summary else ""
        except Exception as e:
            logger.warning(f"2GIS search failed: {e}")
            return ""

    def search(self, query: str) -> str:
        try:
            results = self._tavily.search(query=query, max_results=5)
            if not results.get("results"):
                return "No results found."
            summary = []
            for r in results["results"]:
                summary.append(f"- {r['title']}: {r['content'][:200]}...")
            
            tavily_result = "\n".join(summary)
            
            city_indicators = ["тюмень", "екатеринбург", "москва", "спб", "питер", "новосибирск"]
            needs_local = any(word in query.lower() for word in city_indicators)
            
            if needs_local:
                city = next((w for w in city_indicators if w in query.lower()), "")
                if city:
                    gis_result = self._search_2gis(query, city)
                    if gis_result:
                        return tavily_result + "\n\nЛокальные данные (2GIS):\n" + gis_result
            
            return tavily_result
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()