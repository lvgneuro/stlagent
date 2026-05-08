from __future__ import annotations

import logging

from bot.database import db, Sofa

logger = logging.getLogger(__name__)


class RivalliSearch:
    def __init__(self) -> None:
        self.db = db

    async def search(self, query: str, limit: int = 10) -> list[Sofa]:
        logger.info(f"Searching sofas with query: {query}")
        results = await self.db.search_sofas(query, limit)
        logger.info(f"Found {len(results)} results")
        for r in results[:3]:
            logger.info(f"  Result: name={r.name}, url={r.url}")
        return results

    async def get_all(self, limit: int = 100) -> list[Sofa]:
        sofas = await self.db.get_all_sofas(limit)
        logger.info(f"get_all returned {len(sofas)} sofas")
        return sofas

    async def get_count(self) -> int:
        count = await self.db.get_sofa_count()
        logger.info(f"get_count: {count}")
        return count

    def format_sofa_result(self, sofa: Sofa) -> str:
        text = f"<b>{sofa.name}</b>\n"
        if sofa.category:
            text += f"📁 {sofa.category}\n"
        if sofa.description:
            desc = (
                sofa.description[:200] + "..."
                if len(sofa.description or "") > 200
                else sofa.description
            )
            text += f"{desc}\n"
        text += f"🔗 {sofa.url}"
        return text

    def format_search_results(self, results: list[Sofa], query: str) -> str:
        if not results:
            return f'По запросу "{query}" ничего не найдено в каталоге диванов Rivalli.'
        text = f'Найдено {len(results)} диванов по запросу "{query}":\n\n'
        for i, sofa in enumerate(results[:5], 1):
            text += f"{i}. <b>{sofa.name}</b>\n"
            if sofa.description:
                text += f"   {sofa.description[:100]}...\n"
            text += f"   🔗 {sofa.url}\n\n"
        if len(results) > 5:
            text += f"... и еще {len(results) - 5} диванов"
        return text


rivalli_search = RivalliSearch()
