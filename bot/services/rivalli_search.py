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

        all_cells = re.findall(r"<td[^>]*>([^<]+)</td>", html)
        if len(all_cells) >= 2:
            labels = [all_cells[i] for i in range(0, len(all_cells) - 1, 2)]
            values = [all_cells[i] for i in range(1, len(all_cells), 2)]

            target_labels = {
                "Механизм",
                "Спальное место",
                "Длина",
                "Глубина",
                "Высота",
                "Ширина",
                "Матрас",
                "Каркас",
                "Съемный чехол",
                "Чехол",
                "Ножки",
                "Опоры",
                "Высота сиденья",
                "Глубина сиденья",
                "Наполнитель",
                "Пружинный блок",
                "Высота матраса",
                "Ширина подлокотника",
                "Клиренс",
                "Посадочных мест",
            }
            for label, value in zip(labels, values):
                if label in target_labels and len(value.strip()) > 1:
                    parts.append(f"{label}: {value.strip()[:100]}")
        else:
            matches = re.findall(
                r'<div class="(left|right)">([^<]*)</div>', html
            )
            i = 0
            while i < len(matches):
                cls, val = matches[i]
                if cls == "left":
                    next_val = ""
                    if i + 1 < len(matches) and matches[i + 1][0] == "right":
                        next_val = matches[i + 1][1]
                    label = re.sub(r"<[^>]+>", "", val).strip()
                    value = re.sub(r"<[^>]+>", "", next_val).strip()
                    if label and value and len(value) > 1:
                        parts.append(f"{label}: {value[:100]}")
                    i += 2
                else:
                    i += 1

        desc_match = re.search(
            r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</p>', html, re.IGNORECASE
        )
        if desc_match:
            desc = desc_match.group(1).strip()
            if len(desc) > 10:
                parts.insert(0, desc[:200])

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
        if sofa.features:
            text += f"{sofa.features}\n"
        elif sofa.description:
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
            if sofa.features:
                feats = sofa.features[:150].replace("\n", " | ")
                text += f"   {feats}...\n"
            elif sofa.description:
                text += f"   {sofa.description[:80]}...\n"
            text += f"   🔗 {sofa.url}\n\n"
        if len(results) > 5:
            text += f"... и еще {len(results) - 5} диванов"
        return text


rivalli_search = RivalliSearch()
