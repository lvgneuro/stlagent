from __future__ import annotations

import logging

from bot.database import db, Sofa

logger = logging.getLogger(__name__)


class RivalliSearch:
    def __init__(self) -> None:
        self.db = db

    async def search(self, query: str, limit: int = 10) -> list[Sofa]:
        results = await self.db.search_sofas(query, limit)
        return results

    async def get_all(self, limit: int = 100) -> list[Sofa]:
        return await self.db.get_all_sofas(limit)

    async def get_count(self) -> int:
        return await self.db.get_sofa_count()

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
