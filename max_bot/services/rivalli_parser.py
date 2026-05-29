from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://rivalli.ru"
CATALOG_URL = "https://rivalli.ru/catalog/divany/"

CATEGORY_URLS = [
    "https://rivalli.ru/catalog/divany/",
    "https://rivalli.ru/catalog/divany/pryamye-divany/",
    "https://rivalli.ru/catalog/divany/uglovye-divany/",
    "https://rivalli.ru/catalog/divany/modulnye-divany/",
    "https://rivalli.ru/catalog/divany/kushetki/",
]


@dataclass
class SofaData:
    slug: str
    name: str
    url: str
    category: str | None
    description: str | None
    features: str | None
    image_urls: list[str]


class RivalliParser:
    def __init__(self) -> None:
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "RivalliParser":
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> str | None:
        if not self.session:
            return None
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning(f"Status {resp.status} for {url}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_sofa_links(self, html: str, category: str) -> list[tuple[str, str]]:
        links = []
        pattern = r'<a[^>]+href="(/catalog/divany/[^/"]+/)"[^>]*>'
        matches = re.findall(pattern, html)
        seen_urls = set()

        for match in matches:
            if match == "/catalog/divany/":
                continue
            slug = match.strip("/catalog/divany/").strip("/")
            if not slug or slug.startswith("filter") or slug.startswith("?"):
                continue

            full_url = f"{BASE_URL}{match}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            name = slug.replace("-", " ").title()
            name_match = re.search(
                rf'<a[^>]+href="{re.escape(match)}"[^>]*>([^<]+)</a>',
                html
            )
            if name_match:
                name = name_match.group(1).strip()

            links.append((name, full_url))

        return links

    def extract_sofa_details(self, html: str, url: str) -> SofaData | None:
        slug = url.replace(BASE_URL + "/catalog/divany/", "").strip("/").split("/")[0]
        name_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        name = (
            name_match.group(1).strip()
            if name_match
            else slug.replace("-", " ").title()
        )
        description_match = re.search(
            r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</p>', html, re.IGNORECASE
        )
        description = description_match.group(1).strip() if description_match else None
        if not description:
            desc_pattern = r'">(Д\d+[^<]+)'
            matches = re.findall(desc_pattern, html)
            if matches:
                description = " ".join(matches[:3])
        features_parts = []
        feature_patterns = [
            r">(Механизм[^<]+)<",
            r">(Материал[^<]+)<",
            r">(Размер[^<]+)<",
            r">(Габариты[^<]+)<",
            r">(Спальное место[^<]+)<",
            r">(Каркас[^<]+)<",
        ]
        for pattern in feature_patterns:
            matches = re.findall(pattern, html)
            features_parts.extend(matches)
        features = " | ".join(features_parts[:8]) if features_parts else None
        image_urls = []
        img_pattern = r'<img[^>]+src="(https://rivalli\.ru/upload/iblock/[^"]+\.jpg)"'
        matches = re.findall(img_pattern, html)
        image_urls = list(dict.fromkeys(matches))[:5]
        return SofaData(
            slug=slug,
            name=name,
            url=url,
            category=None,
            description=description,
            features=features,
            image_urls=image_urls,
        )

    async def parse_catalog_page(self, url: str) -> list[tuple[str, str]]:
        html = await self.fetch_page(url)
        if not html:
            return []
        return self.extract_sofa_links(html, url.split("/")[-2] if url.endswith("/") else url.split("/")[-1])

    async def parse_sofa_page(self, url: str) -> SofaData | None:
        html = await self.fetch_page(url)
        if not html:
            return None
        return self.extract_sofa_details(html, url)

    async def index_all_sofas(self) -> list[SofaData]:
        all_sofas: list[SofaData] = []
        seen_urls = set()
        for cat_url in CATEGORY_URLS:
            logger.info(f"Parsing category: {cat_url}")
            sofa_links = await self.parse_catalog_page(cat_url)
            logger.info(f"Found {len(sofa_links)} links in category")
            for name, url in sofa_links:
                if url not in seen_urls:
                    seen_urls.add(url)
                    await asyncio.sleep(0.5)
                    sofa = await self.parse_sofa_page(url)
                    if sofa:
                        all_sofas.append(sofa)
                        logger.info(f"Parsed: {sofa.name}")
                    else:
                        logger.warning(f"Failed to parse: {url}")
        logger.info(f"Total sofas indexed: {len(all_sofas)}")
        return all_sofas


async def run_indexing() -> list[SofaData]:
    async with RivalliParser() as parser:
        return await parser.index_all_sofas()