from __future__ import annotations

import logging
import re

import aiohttp

from bot.database import db, Sofa

logger = logging.getLogger(__name__)


class RivalliSearch:
    def __init__(self) -> None:
        self.db = db
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                }
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_sofa_details(self, url: str) -> str | None:
        session = await self._get_session()
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

        parts = []
        patterns = [
            (r"Механизм[:\s]*([^\n<]+)", "Механизм"),
            (r"Спальное место[:\s]*([^\n<]+)", "Спальное место"),
            (r"Длина[:\s]*([^\n<]+)", "Длина"),
            (r"Ширина[:\s]*([^\n<]+)", "Ширина"),
            (r"Глубина[:\s]*([^\n<]+)", "Глубина"),
            (r"Высота[:\s]*([^\n<]+)", "Высота"),
            (r"Глубина сиденья[:\s]*([^\n<]+)", "Глубина сиденья"),
            (r"Высота сиденья[:\s]*([^\n<]+)", "Высота сиденья"),
            (r"Материал[:\s]*([^\n<]+)", "Материал"),
            (r"Каркас[:\s]*([^\n<]+)", "Каркас"),
            (r"Ножки[:\s]*([^\n<]+)", "Ножки"),
            (r"Матрас[:\s]*([^\n<]+)", "Матрас"),
            (r"Наполнитель[:\s]*([^\n<]+)", "Наполнитель"),
        ]

        for pattern, label in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                val = match.group(1).strip()[:80]
                if val and len(val) > 2:
                    parts.append(f"{label}: {val}")

        desc_match = re.search(
            r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</p>', html, re.IGNORECASE
        )
        if not desc_match:
            desc_match = re.search(
                r'id="description"[^>]*>([^<]+)', html, re.IGNORECASE
            )
        if not desc_match:
            desc_match = re.search(r"Диван[^-]+-\s*([^\n<]+)", html)
        if desc_match:
            desc = desc_match.group(1).strip()
            if len(desc) > 10:
                parts.insert(0, desc[:200])

        spec_patterns = [
            r"Механизм[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Спальное место[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Длина[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Глубина[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Высота[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Ширина[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Высота сиденья[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Глубина сиденья[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Матрас[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Каркас[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Чехол[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Ножки[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Наполнитель[\s\n]*[:\.]*\s*([^\n<]+)",
            r"Пружинный блок[\s\n]*[:\.]*\s*([^\n<]+)",
        ]

        for pattern in spec_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                val = match.group(1).strip()[:80]
                if val and len(val) > 2 and val not in ["", "-"]:
                    label = pattern.replace("[\s\n]*[:\.]*\s*", "").replace(
                        "[\s\n]*", ""
                    )
                    if f"{label}:" not in "\n".join(parts):
                        parts.append(f"{label}: {val}")

        return "\n".join(parts) if parts else None

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
